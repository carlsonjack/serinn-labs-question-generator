"""Tests for multi-vertical input resolution (load_normalized_bundle prerequisites)."""

from __future__ import annotations

from pathlib import Path

from core.parsers.contracts import SourceRole
from core.parsers.service import resolve_input_scan_jobs


def test_legacy_mlb_slots_resolve_two_paths(tmp_path: Path) -> None:
    (tmp_path / "schedule.xlsx").touch()
    (tmp_path / "stats.xlsx").touch()
    settings = {
        "inputs": {
            "files": {
                "mlb": {
                    "event_source": "schedule.xlsx",
                    "metric_source": "stats.xlsx",
                },
            },
        },
    }
    fc = settings["inputs"]["files"]["mlb"]
    jobs, issues = resolve_input_scan_jobs(
        settings,
        category_key="mlb",
        input_dir=tmp_path,
        file_config=fc,
        matched_pkg_key="mlb",
    )
    assert not issues
    assert len(jobs) == 2
    assert jobs[0][1] == SourceRole.EVENT_SOURCE
    assert jobs[1][1] == SourceRole.METRIC_SOURCE


def test_dynamic_package_requires_file_roles(tmp_path: Path) -> None:
    (tmp_path / "f1_schedule.xlsx").touch()
    settings = {
        "inputs": {
            "files": {"f1": {"schedule": "f1_schedule.xlsx"}},
        },
    }
    fc = settings["inputs"]["files"]["f1"]
    jobs, issues = resolve_input_scan_jobs(
        settings,
        category_key="f1",
        input_dir=tmp_path,
        file_config=fc,
        matched_pkg_key="f1",
    )
    assert not jobs
    assert issues and issues[0].code == "missing_file_roles"


def test_dynamic_f1_single_slot(tmp_path: Path) -> None:
    (tmp_path / "f1_schedule.xlsx").touch()
    settings = {
        "inputs": {
            "files": {"F1": {"schedule": "f1_schedule.xlsx"}},
            "file_roles": {"F1": {"schedule": "event_source"}},
        },
    }
    fc = settings["inputs"]["files"]["F1"]
    jobs, issues = resolve_input_scan_jobs(
        settings,
        category_key="F1",
        input_dir=tmp_path,
        file_config=fc,
        matched_pkg_key="F1",
    )
    assert not issues
    assert len(jobs) == 1
    assert jobs[0][1] == SourceRole.EVENT_SOURCE
