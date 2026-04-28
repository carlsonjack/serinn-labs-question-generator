"""Flask application for the local web UI."""

from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from core.config import load_settings, load_settings_disk_only, save_settings_yaml
from core.csv_export import DEFAULT_OUTPUT_DIR
from core.input_slots import (
    get_files_map_for_category,
    get_inputs_category_key,
    iter_input_slots,
    list_input_categories,
    normalize_inputs_files,
)
from core.pipeline import PipelineResult, pipeline_result_to_job_dict, run_pipeline
from core.template_config.loader import load_template_dir, resolve_templates_directory
from core.template_config.schema import parse_template_dict
from core.template_ui import (
    filter_templates_for_package,
    infer_subcategory_for_package,
    template_to_ui_dict,
)
from core.template_upload import parse_uploaded_template_file

_ROOT = Path(__file__).resolve().parent.parent
_LOCK = threading.Lock()
_JOBS: dict[str, "JobState"] = {}
_ACTIVE_RUN = False


def _is_safe_download_name(name: str) -> bool:
    if not name or name != Path(name).name:
        return False
    if ".." in name or "/" in name or "\\" in name:
        return False
    return bool(secure_filename(name) == name)


@dataclass
class JobState:
    state: str  # queued | running | succeeded | failed
    phase: str = ""
    current_step: int = 0
    total_steps: int = 0
    error: str | None = None
    result: PipelineResult | None = None
    payload: dict[str, Any] = field(default_factory=dict)


def _template_meta_for_package(
    settings: dict[str, Any], category_key: str
) -> tuple[list[dict[str, Any]], str]:
    """Return template cards and the display subcategory for ``category_key``."""

    tpl_dir = resolve_templates_directory(settings)
    templates = load_template_dir(tpl_dir)
    te = settings.get("templates_enabled") or {}
    matched = filter_templates_for_package(templates.values(), category_key)
    template_meta = [
        template_to_ui_dict(t, enabled=bool(te.get(t.id, True)))
        for t in matched
    ]
    template_subcategory = infer_subcategory_for_package(
        templates.values(),
        category_key,
        fallback=str(settings.get("subcategory") or ""),
    )
    return template_meta, template_subcategory


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")

    @app.get("/")
    def index() -> str:
        settings = load_settings()
        ick = get_inputs_category_key(settings)
        template_meta, template_subcategory = _template_meta_for_package(settings, ick)
        input_slots = iter_input_slots(settings, ick)
        input_categories = list_input_categories(settings)
        if not input_categories:
            input_categories = [ick]
        inputs_block = settings.get("inputs") or {}
        files_root = inputs_block.get("files") if isinstance(inputs_block, dict) else {}
        if not isinstance(files_root, dict):
            files_root = {}
        return render_template(
            "index.html",
            settings=settings,
            template_meta=template_meta,
            output_dir=str(DEFAULT_OUTPUT_DIR),
            input_category_key=ick,
            input_categories=input_categories,
            input_slots=input_slots,
            inputs_files_map=files_root,
            template_subcategory=template_subcategory,
        )

    @app.post("/api/inputs-files")
    def api_save_inputs_files() -> Any:
        """Replace ``inputs.files`` from JSON ``{ \"files\": { pkg: { slot: name } } }``."""

        if not request.is_json:
            return jsonify({"error": "Expected application/json"}), 400
        body = request.get_json(silent=True) or {}
        try:
            normalized = normalize_inputs_files(body.get("files"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        current = load_settings_disk_only()
        inputs_prev = current.get("inputs") or {}
        prev_cat = inputs_prev.get("category_key")
        keys = sorted(normalized.keys())
        if isinstance(prev_cat, str) and prev_cat.strip() in normalized:
            cat = prev_cat.strip()
        else:
            cat = keys[0]
        save_settings_yaml(
            {"_inputs_files": normalized, "inputs": {"category_key": cat}}
        )
        return jsonify(
            {
                "ok": True,
                "files": normalized,
                "category_key": cat,
            }
        )

    @app.get("/api/input-slots")
    def api_input_slots() -> Any:
        settings = load_settings()
        cat = (request.args.get("category") or "").strip() or get_inputs_category_key(
            settings
        )
        files_root = settings.get("inputs", {}).get("files") or {}
        if cat not in files_root:
            return jsonify({"error": f"Unknown input package: {cat!r}"}), 400
        slots = iter_input_slots(settings, cat)
        template_meta, template_subcategory = _template_meta_for_package(settings, cat)
        return jsonify(
            {
                "category_key": cat,
                "slots": slots,
                "template_meta": template_meta,
                "template_subcategory": template_subcategory,
            }
        )

    @app.post("/upload/templates")
    def upload_templates() -> Any:
        """Save one or more validated template files into ``templates_directory``."""

        settings = load_settings()
        tpl_dir = resolve_templates_directory(settings)
        tpl_dir.mkdir(parents=True, exist_ok=True)

        files = [f for f in request.files.getlist("files") if f and f.filename]
        if not files:
            one = request.files.get("file")
            if one and one.filename:
                files = [one]
        if not files:
            return jsonify({"error": "No template file uploaded."}), 400

        saved: list[dict[str, str]] = []
        errors: list[dict[str, str]] = []
        upload_ids: set[str] = set()

        for fh in files:
            name = fh.filename or ""
            try:
                raw_text = fh.read()
                blocks = parse_uploaded_template_file(name, raw_text)
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                errors.append({"filename": name, "error": str(exc)})
                continue

            for block_index, data in enumerate(blocks, start=1):
                label = name if len(blocks) == 1 else f"{name} [block {block_index}]"
                try:
                    parsed = parse_template_dict(data)
                except ValueError as exc:
                    errors.append({"filename": label, "error": str(exc)})
                    continue
                if parsed.id in upload_ids:
                    errors.append(
                        {
                            "filename": label,
                            "error": f"Duplicate template id in upload: {parsed.id!r}",
                        }
                    )
                    continue
                upload_ids.add(parsed.id)
                safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", parsed.id).strip("_") or "template"
                out_name = f"{safe_id}.json"
                out_path = tpl_dir / out_name
                with out_path.open("w", encoding="utf-8") as out_f:
                    json.dump(data, out_f, indent=2, ensure_ascii=False)
                    out_f.write("\n")
                saved.append({"id": parsed.id, "filename": out_name})

        disk = load_settings_disk_only()
        te = dict(disk.get("templates_enabled") or {})
        for item in saved:
            te[item["id"]] = True
        save_settings_yaml({"templates_enabled": te})

        return jsonify(
            {
                "ok": len(saved) > 0,
                "saved": saved,
                "errors": errors,
                "reload": True,
            }
        )

    @app.post("/upload")
    def upload() -> Any:
        settings = load_settings()
        input_dir = _ROOT / settings.get("inputs", {}).get("directory", "inputs")
        cat = (request.form.get("category_key") or "").strip() or get_inputs_category_key(
            settings
        )
        files_map = get_files_map_for_category(settings, cat)
        if not files_map:
            return jsonify(
                {"error": f"No input files configured for package {cat!r}."}
            ), 400

        input_dir.mkdir(parents=True, exist_ok=True)

        saved: list[dict[str, str]] = []
        any_file = False
        for slot_id, target_name in files_map.items():
            fh = request.files.get(slot_id)
            if fh is None or fh.filename == "":
                continue
            any_file = True
            if not fh.filename.lower().endswith(".xlsx"):
                return jsonify({"error": f"Only .xlsx allowed: {fh.filename!r}"}), 400
            dest = input_dir / target_name
            fh.save(str(dest))
            saved.append({"slot_id": slot_id, "filename": target_name})

        if not any_file:
            return jsonify(
                {
                    "error": "No files provided. Choose at least one file "
                    f"({', '.join(sorted(files_map.keys()))})."
                }
            ), 400

        return jsonify({"ok": True, "category_key": cat, "saved": saved})

    @app.post("/run")
    def run() -> Any:
        global _ACTIVE_RUN
        if not request.is_json:
            return jsonify({"error": "Expected application/json"}), 400

        payload = request.get_json(silent=True) or {}
        with _LOCK:
            if _ACTIVE_RUN:
                return (
                    jsonify(
                        {
                            "error": "A generation job is already running. "
                            "Wait for it to finish before starting another."
                        }
                    ),
                    409,
                )

        try:
            updates = _build_settings_updates_from_payload(payload)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        save_settings_yaml(updates)
        settings = load_settings()

        job_id = uuid.uuid4().hex
        with _LOCK:
            _ACTIVE_RUN = True
            _JOBS[job_id] = JobState(state="queued", phase="Queued")

        def work() -> None:
            global _ACTIVE_RUN
            try:
                with _LOCK:
                    st0 = _JOBS[job_id]
                    st0.state = "running"
                    st0.phase = "Starting pipeline"
                result_holder: list[PipelineResult] = []

                def progress(phase: str, cur: int, tot: int) -> None:
                    with _LOCK:
                        st = _JOBS.get(job_id)
                        if st:
                            st.phase = phase
                            st.current_step = cur
                            st.total_steps = tot

                result_holder.append(run_pipeline(settings, progress=progress))

                with _LOCK:
                    st = _JOBS[job_id]
                    st.result = result_holder[0]
                    st.state = "succeeded" if result_holder[0].success else "failed"
                    st.phase = "Done" if result_holder[0].success else "Failed"
                    if not result_holder[0].success and result_holder[0].message:
                        st.error = result_holder[0].message
                    st.payload = pipeline_result_to_job_dict(result_holder[0])
            except Exception as exc:  # noqa: BLE001
                with _LOCK:
                    st = _JOBS[job_id]
                    st.state = "failed"
                    st.error = str(exc)
                    st.phase = "Failed"
                    st.payload = {"success": False, "message": str(exc)}
            finally:
                with _LOCK:
                    _ACTIVE_RUN = False

        t = threading.Thread(target=work, daemon=True)
        t.start()

        return jsonify({"job_id": job_id})

    @app.get("/run/status/<job_id>")
    def run_status(job_id: str) -> Any:
        with _LOCK:
            job = _JOBS.get(job_id)
        if job is None:
            return jsonify({"error": "Unknown job_id"}), 404

        body: dict[str, Any] = {
            "state": job.state,
            "phase": job.phase,
            "current_step": job.current_step,
            "total_steps": job.total_steps,
        }
        if job.error:
            body["error"] = job.error
        if job.state in ("succeeded", "failed"):
            body.update(job.payload)
        return jsonify(body)

    @app.get("/download/<filename>")
    def download(filename: str) -> Any:
        if not _is_safe_download_name(filename):
            abort(404)
        target = Path(DEFAULT_OUTPUT_DIR) / filename
        try:
            target.resolve().relative_to(Path(DEFAULT_OUTPUT_DIR).resolve())
        except ValueError:
            abort(404)
        if not target.is_file():
            abort(404)
        return send_from_directory(
            str(DEFAULT_OUTPUT_DIR),
            filename,
            as_attachment=True,
        )

    return app


def _build_settings_updates_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Map JSON body from the SPA into settings YAML updates."""

    updates: dict[str, Any] = {}

    if "category_id" in payload:
        updates["category_id"] = str(payload.get("category_id") or "")

    if "subcategory" in payload:
        updates["subcategory"] = str(payload.get("subcategory") or "MLB")

    if "top_n_per_team" in payload:
        updates["top_n_per_team"] = int(payload.get("top_n_per_team") or 3)

    if "date_start" in payload or "date_end" in payload:
        base_df = dict(load_settings_disk_only().get("date_filter") or {})
        if "date_start" in payload:
            base_df["start"] = str(payload.get("date_start") or "")
        if "date_end" in payload:
            base_df["end"] = str(payload.get("date_end") or "")
        updates["date_filter"] = base_df

    if "templates_enabled" in payload and isinstance(payload["templates_enabled"], dict):
        updates["templates_enabled"] = {
            k: bool(v) for k, v in payload["templates_enabled"].items()
        }

    if "input_category_key" in payload:
        ick = str(payload.get("input_category_key") or "").strip()
        if ick:
            updates["inputs"] = {"category_key": ick}

    if "max_generated_questions" in payload:
        v = payload.get("max_generated_questions")
        if v is None or v == "":
            updates["max_generated_questions"] = None
        else:
            updates["max_generated_questions"] = int(v)

    if "_inputs_files" in payload and payload.get("_inputs_files") is not None:
        updates["_inputs_files"] = normalize_inputs_files(payload.get("_inputs_files"))

    return updates


app = create_app()
