"""High-level entrypoints for category input normalization."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .contracts import NormalizedBundle, SourceRole, ValidationIssue, ValidationSeverity
from .detector import inspect_file
from .profiles import save_profile
from .registry import get_category_normalizer
from .season_merge import infer_merge_profile_options

# Register built-in category normalizers.
from .mlb import normalizer as _mlb_normalizer  # noqa: F401


def load_normalized_bundle(
    settings: Mapping[str, Any],
    *,
    category_key: str = "mlb",
) -> NormalizedBundle:
    """Load, detect, and normalize the configured inputs for one category."""

    input_dir = Path(settings.get("inputs", {}).get("directory", "inputs"))
    file_config = settings.get("inputs", {}).get("files", {}).get(category_key, {})
    event_path = input_dir / file_config.get("event_source", "schedule.xlsx")
    metric_path = input_dir / file_config.get("metric_source", "stats.xlsx")

    issues: list[ValidationIssue] = []
    detected_files = []
    for path, role, sheet_terms in (
        (event_path, SourceRole.EVENT_SOURCE, ()),
        (metric_path, SourceRole.METRIC_SOURCE, ("2026",)),
    ):
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
            category_key=category_key,
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
            save_profile(detection.detected_file.profile_used)

    if any(issue.severity == ValidationSeverity.ERROR for issue in issues):
        return NormalizedBundle(issues=issues)

    bundle = get_category_normalizer(category_key)().normalize(detected_files, settings)
    bundle.issues = [*issues, *bundle.issues]
    return bundle

