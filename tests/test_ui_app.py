"""Flask UI routes (Epic 8)."""

from __future__ import annotations

import io
import json
import time
from unittest.mock import patch

import pytest

from core.pipeline import PipelineResult
from core.template_config.schema import QuestionTemplate
from ui.app import create_app


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_download_rejects_traversal(client):
    rv = client.get("/download/../secrets")
    assert rv.status_code == 404


def test_download_requires_file_under_outputs(client, tmp_path, monkeypatch):
    monkeypatch.setattr("ui.app.DEFAULT_OUTPUT_DIR", tmp_path)
    safe = tmp_path / "out.csv"
    safe.write_text("a,b\n", encoding="utf-8")

    rv = client.get("/download/out.csv")
    assert rv.status_code == 200
    assert b"a,b" in rv.data


def test_download_missing_file_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr("ui.app.DEFAULT_OUTPUT_DIR", tmp_path)
    rv = client.get("/download/nope.csv")
    assert rv.status_code == 404


def test_run_returns_409_when_job_active(client):
    def slow_run(*_a, **_k):
        time.sleep(0.4)
        return PipelineResult(success=True)

    fake_settings = {
        "openai_api_key": "sk-test",
        "category_id": "x",
        "subcategory": "MLB",
        "date_filter": {"start": "2026-05-15", "end": "2026-06-01"},
        "templates_enabled": {},
        "inputs": {"directory": "inputs", "files": {"mlb": {}}},
    }

    with (
        patch("ui.app.save_settings_yaml"),
        patch("ui.app.load_settings", return_value=fake_settings),
        patch("ui.app.run_pipeline", side_effect=slow_run),
    ):
        r1 = client.post(
            "/run",
            json={
                "category_id": "x",
                "subcategory": "MLB",
                "top_n_per_team": 2,
                "date_start": "2026-05-15",
                "date_end": "2026-06-01",
                "templates_enabled": {},
            },
        )
        assert r1.status_code == 200
        r2 = client.post(
            "/run",
            json={
                "category_id": "x",
                "subcategory": "MLB",
                "top_n_per_team": 2,
                "date_start": "2026-05-15",
                "date_end": "2026-06-01",
                "templates_enabled": {},
            },
        )
        assert r2.status_code == 409
    time.sleep(0.5)


def test_run_status_unknown_job(client):
    rv = client.get("/run/status/not-a-real-id")
    assert rv.status_code == 404


def test_upload_requires_xlsx(client):
    rv = client.post("/upload", data={})
    assert rv.status_code == 400


def test_upload_templates_writes_json(client, tmp_path, monkeypatch):
    monkeypatch.setattr("ui.app.resolve_templates_directory", lambda _s: tmp_path)
    monkeypatch.setattr("ui.app.load_settings_disk_only", lambda: {"templates_enabled": {}})
    monkeypatch.setattr("ui.app.save_settings_yaml", lambda _u: None)

    tpl = {
        "id": "ui_test_tpl",
        "subcategory": "MLB",
        "question_family": "event",
        "question": "Smoke test question?",
        "answer_type": "yes_no",
        "answer_options": "Yes||No",
        "priority": "false",
        "requires_entities": False,
    }
    body = json.dumps(tpl)
    rv = client.post(
        "/upload/templates",
        data={"file": (io.BytesIO(body.encode("utf-8")), "upload.json")},
        content_type="multipart/form-data",
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["ok"] is True
    assert any(x["id"] == "ui_test_tpl" for x in data["saved"])
    out = tmp_path / "ui_test_tpl.json"
    assert out.is_file()
    assert "Smoke test" in out.read_text(encoding="utf-8")


def test_upload_templates_writes_multiple_templates_from_csv(client, tmp_path, monkeypatch):
    monkeypatch.setattr("ui.app.resolve_templates_directory", lambda _s: tmp_path)
    monkeypatch.setattr("ui.app.load_settings_disk_only", lambda: {"templates_enabled": {}})
    monkeypatch.setattr("ui.app.save_settings_yaml", lambda _u: None)

    body = (
        "id,subcategory,question_family,question,answer_type,answer_options,priority,requires_entities\n"
        "csv_tpl_one,MLB,event,First?,yes_no,Yes||No,false,false\n"
        "id,subcategory,question_family,question,answer_type,answer_options,priority,requires_entities,stat_column,top_n_per_team\n"
        "csv_tpl_two,MLB,entity_stat,Second?,multiple_choice,{entity_options},false,true,HR,3\n"
    )
    rv = client.post(
        "/upload/templates",
        data={"file": (io.BytesIO(body.encode("utf-8")), "upload.csv")},
        content_type="multipart/form-data",
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["ok"] is True
    assert [x["id"] for x in data["saved"]] == ["csv_tpl_one", "csv_tpl_two"]
    assert (tmp_path / "csv_tpl_one.json").is_file()
    assert (tmp_path / "csv_tpl_two.json").is_file()


def test_upload_templates_rejects_duplicate_ids_in_csv(client, tmp_path, monkeypatch):
    monkeypatch.setattr("ui.app.resolve_templates_directory", lambda _s: tmp_path)
    monkeypatch.setattr("ui.app.load_settings_disk_only", lambda: {"templates_enabled": {}})
    monkeypatch.setattr("ui.app.save_settings_yaml", lambda _u: None)

    body = (
        "id,subcategory,question_family,question,answer_type,answer_options,priority,requires_entities\n"
        "dup_tpl,MLB,event,First?,yes_no,Yes||No,false,false\n"
        "id,subcategory,question_family,question,answer_type,answer_options,priority,requires_entities\n"
        "dup_tpl,MLB,event,Second?,yes_no,Yes||No,false,false\n"
    )
    rv = client.post(
        "/upload/templates",
        data={"file": (io.BytesIO(body.encode("utf-8")), "upload.csv")},
        content_type="multipart/form-data",
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["ok"] is True
    assert [x["id"] for x in data["saved"]] == ["dup_tpl"]
    assert "Duplicate template id in upload" in data["errors"][0]["error"]


def test_api_input_slots_returns_package_filtered_templates(client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "ui.app.load_settings",
        lambda: {
            "subcategory": "MLB",
            "templates_enabled": {"mlb_a": True, "ent_a": False},
            "inputs": {
                "directory": "inputs",
                "category_key": "mlb",
                "files": {
                    "mlb": {"event_source": "schedule.xlsx"},
                    "entertainment": {"event_source": "ent.xlsx"},
                },
            },
        },
    )
    monkeypatch.setattr("ui.app.resolve_templates_directory", lambda _s: tmp_path)
    monkeypatch.setattr(
        "ui.app.load_template_dir",
        lambda _p: {
            "mlb_a": QuestionTemplate(
                id="mlb_a",
                subcategory="MLB",
                question_family="event",
                question="MLB question?",
                answer_type="yes_no",
                answer_options="Yes||No",
                priority="false",
                requires_entities=False,
            ),
            "ent_a": QuestionTemplate(
                id="ent_a",
                subcategory="Entertainment",
                question_family="event",
                question="Entertainment question?",
                answer_type="yes_no",
                answer_options="Yes||No",
                priority="false",
                requires_entities=False,
            ),
        },
    )

    rv = client.get("/api/input-slots?category=mlb")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["category_key"] == "mlb"
    assert [x["id"] for x in data["template_meta"]] == ["mlb_a"]
    assert data["template_subcategory"] == "MLB"


def test_api_save_inputs_files(client, tmp_path, monkeypatch):
    cfg = tmp_path / "settings.yaml"
    monkeypatch.setattr("core.config._SETTINGS", cfg)
    monkeypatch.setattr("core.config._SETTINGS_LOCAL", tmp_path / "nope.local.yaml")

    cfg.write_text(
        "inputs:\n"
        "  directory: inputs\n"
        "  category_key: mlb\n"
        "  files:\n"
        "    mlb:\n"
        "      event_source: a.xlsx\n",
        encoding="utf-8",
    )
    rv = client.post(
        "/api/inputs-files",
        json={
            "files": {
                "mlb": {
                    "event_source": "schedule.xlsx",
                    "metric_source": "stats.xlsx",
                }
            }
        },
    )
    assert rv.status_code == 200
    j = rv.get_json()
    assert j["ok"] is True
    assert j["category_key"] == "mlb"
    from core.config import load_settings_disk_only

    data = load_settings_disk_only()
    assert data["inputs"]["files"]["mlb"]["metric_source"] == "stats.xlsx"


def test_api_save_inputs_files_rejects_empty(client):
    rv = client.post("/api/inputs-files", json={"files": {}})
    assert rv.status_code == 400


def test_save_settings_yaml_roundtrip(tmp_path, monkeypatch):
    from core.config import load_settings_disk_only, save_settings_yaml

    cfg = tmp_path / "settings.yaml"
    monkeypatch.setattr("core.config._SETTINGS", cfg)
    monkeypatch.setattr("core.config._SETTINGS_LOCAL", tmp_path / "nope.yaml")

    cfg.write_text(
        "category_id: \"x\"\ndate_filter:\n  start: \"2026-01-01\"\n  end: \"2026-02-01\"\n",
        encoding="utf-8",
    )
    save_settings_yaml({"subcategory": "MLB", "top_n_per_team": 4})
    data = load_settings_disk_only()
    assert data["subcategory"] == "MLB"
    assert data["top_n_per_team"] == 4
    assert data["date_filter"]["start"] == "2026-01-01"
