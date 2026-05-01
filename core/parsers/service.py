"""High-level entrypoints for category input normalization."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .contracts import NormalizedBundle, SourceRole, ValidationIssue, ValidationSeverity
from .detector import inspect_file
from .profiles import save_profile
from .registry import get_category_normalizer, list_registered_categories
from .season_merge import infer_merge_profile_options

# Register built-in category normalizers.
from .f1 import normalizer as _f1_normalizer  # noqa: F401
from .mlb import normalizer as _mlb_normalizer  # noqa: F401


def _match_inputs_package(
    files_root: Mapping[str, Any],
    category_key: str,
) -> tuple[str | None, dict[str, Any]]:
    """Return the YAML storage key for ``category_key`` and its slot → filename map."""

    if not isinstance(files_root, dict):
        return None, {}
    ck = category_key.strip()
    if ck in files_root and isinstance(files_root[ck], dict):
        return ck, files_root[ck]
    lower = ck.lower()
    for k, v in files_root.items():
        if isinstance(k, str) and isinstance(v, dict) and k.lower() == lower:
            return k, v
    return None, {}


def _legacy_two_slot_shape(file_config: dict[str, Any]) -> bool:
    """MLB-style ``event_source`` + ``metric_source`` filenames."""

    return (
        isinstance(file_config, dict)
        and "event_source" in file_config
        and "metric_source" in file_config
    )


def _file_roles_for_package(
    settings: Mapping[str, Any],
    matched_pkg_key: str,
) -> dict[str, str] | None:
    roles_root = (settings.get("inputs") or {}).get("file_roles") or {}
    if not isinstance(roles_root, dict):
        return None
    mk = matched_pkg_key.strip()
    if mk in roles_root and isinstance(roles_root[mk], dict):
        return {str(k): str(v) for k, v in roles_root[mk].items()}
    lower = mk.lower()
    for k, v in roles_root.items():
        if isinstance(k, str) and isinstance(v, dict) and k.lower() == lower:
            return {str(sk): str(sv) for sk, sv in v.items()}
    return None


def _metric_sheet_terms(_settings: Mapping[str, Any]) -> tuple[str, ...]:
    """Optional hook; default picks sheets whose name hints at season."""

    return ("2026",)


def resolve_input_scan_jobs(
    settings: Mapping[str, Any],
    *,
    category_key: str,
    input_dir: Path,
    file_config: dict[str, Any],
    matched_pkg_key: str,
) -> tuple[list[tuple[Path, SourceRole, tuple[str, ...]]], list[ValidationIssue]]:
    """Build (path, role, sheet_terms) jobs for detection passes."""

    issues: list[ValidationIssue] = []
    jobs: list[tuple[Path, SourceRole, tuple[str, ...]]] = []

    if _legacy_two_slot_shape(file_config):
        jobs.append(
            (
                input_dir / str(file_config["event_source"]),
                SourceRole.EVENT_SOURCE,
                (),
            )
        )
        jobs.append(
            (
                input_dir / str(file_config["metric_source"]),
                SourceRole.METRIC_SOURCE,
                _metric_sheet_terms(settings),
            )
        )
        return jobs, issues

    role_map = _file_roles_for_package(settings, matched_pkg_key)
    if not role_map:
        issues.append(
            ValidationIssue(
                code="missing_file_roles",
                message=(
                    f"Package {matched_pkg_key!r} needs inputs.file_roles[{matched_pkg_key!r}] "
                    "mapping each slot id to a SourceRole (e.g. event_source, metric_source)."
                ),
                severity=ValidationSeverity.ERROR,
            )
        )
        return [], issues

    for slot_id, fname in sorted(file_config.items()):
        role_name = role_map.get(slot_id)
        if not role_name:
            issues.append(
                ValidationIssue(
                    code="missing_slot_role",
                    message=(
                        f"No role configured for slot {slot_id!r} under "
                        f"inputs.file_roles for package {matched_pkg_key!r}."
                    ),
                    severity=ValidationSeverity.ERROR,
                )
            )
            continue
        try:
            role = SourceRole(str(role_name).strip())
        except ValueError:
            issues.append(
                ValidationIssue(
                    code="invalid_source_role",
                    message=f"Invalid SourceRole for slot {slot_id!r}: {role_name!r}.",
                    severity=ValidationSeverity.ERROR,
                )
            )
            continue
        terms = _metric_sheet_terms(settings) if role == SourceRole.METRIC_SOURCE else ()
        jobs.append((input_dir / str(fname), role, terms))

    return jobs, issues


def load_normalized_bundle(
    settings: Mapping[str, Any],
    *,
    category_key: str = "mlb",
) -> NormalizedBundle:
    """Load, detect, and normalize the configured inputs for one category."""

    registry_ck = category_key.strip().lower()
    input_dir = Path(settings.get("inputs", {}).get("directory", "inputs"))
    files_root = (settings.get("inputs") or {}).get("files") or {}
    matched_pkg_key, file_config = _match_inputs_package(files_root, category_key)

    pre_issues: list[ValidationIssue] = []
    if matched_pkg_key is None or not isinstance(file_config, dict):
        pre_issues.append(
            ValidationIssue(
                code="unknown_input_package",
                message=(
                    f"No inputs.files entry for package {category_key!r}. "
                    f"Known packages: {sorted(str(k) for k in files_root.keys())}"
                ),
                severity=ValidationSeverity.ERROR,
            )
        )
        return NormalizedBundle(issues=pre_issues)

    jobs, role_issues = resolve_input_scan_jobs(
        settings,
        category_key=category_key,
        input_dir=input_dir,
        file_config=file_config,
        matched_pkg_key=matched_pkg_key,
    )
    pre_issues.extend(role_issues)

    issues: list[ValidationIssue] = []
    detected_files = []

    for path, role, sheet_terms in jobs:
        if not path.is_file():
            issues.append(
                ValidationIssue(
                    code="missing_input_file",
                    message=f"Missing input file: {path}",
                    severity=ValidationSeverity.ERROR,
                    file_path=str(path),
                    source_role=role,
                )
            )
            continue
        detection = inspect_file(
            path,
            category_key=registry_ck,
            preferred_role=role,
            preferred_sheet_terms=sheet_terms,
        )
        if (
            role == SourceRole.METRIC_SOURCE
            and detection.detected_file.profile_used is not None
            and len(detection.sheet_detections) > 1
        ):
            detection.detected_file.profile_used.normalizer_options.update(
                infer_merge_profile_options(detection)
            )
        issues.extend(detection.issues)
        detected_files.append(detection.detected_file)
        if settings.get("parsing", {}).get("persist_profiles", True):
            if detection.detected_file.profile_used is not None:
                save_profile(detection.detected_file.profile_used)

    issues = [*pre_issues, *issues]

    if any(issue.severity == ValidationSeverity.ERROR for issue in issues):
        return NormalizedBundle(issues=issues)

    try:
        normalizer_cls = get_category_normalizer(registry_ck)
    except KeyError:
        known = ", ".join(list_registered_categories()) or "<none>"
        return NormalizedBundle(
            issues=[
                ValidationIssue(
                    code="unknown_category_normalizer",
                    message=(
                        f"No normalizer registered for {registry_ck!r}. "
                        f"Known categories: {known}"
                    ),
                    severity=ValidationSeverity.ERROR,
                )
            ]
        )

    try:
        bundle = normalizer_cls().normalize(detected_files, settings)
    except ValueError as exc:
        return NormalizedBundle(
            issues=[
                ValidationIssue(
                    code="normalizer_error",
                    message=str(exc),
                    severity=ValidationSeverity.ERROR,
                )
            ]
        )

    bundle.issues = [*issues, *bundle.issues]
    return bundle
