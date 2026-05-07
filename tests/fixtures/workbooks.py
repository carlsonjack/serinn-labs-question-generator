"""Programmatic .xlsx builders for integration tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_mlb_schedule_minimal(
    path: Path,
    *,
    rows: list[dict[str, object]] | None = None,
) -> Path:
    """Minimal MLB schedule workbook detected without local client inputs."""

    data = rows or [
        {
            "event_id": "MLBTEST001",
            "event_date": "2026-05-15",
            "event_time": "21:40:00",
            "home_team": "Athletics",
            "away_team": "Giants",
        },
        {
            "event_id": "MLBTEST002",
            "event_date": "2026-05-16",
            "event_time": "19:05:00",
            "home_team": "New York Yankees",
            "away_team": "New York Mets",
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(data).to_excel(writer, sheet_name="MLB Schedule", index=False)
    return path


def write_mlb_stats_minimal(
    path: Path,
    *,
    rows: list[dict[str, object]] | None = None,
) -> Path:
    """Minimal MLB stats workbook with teams matching ``write_mlb_schedule_minimal``."""

    data = rows or [
        {"Player": "Athletics Slugger", "Team": "ATH", "HR": 12, "RBI": 44, "SB": 3, "WAR": 2.1},
        {"Player": "Giants Slugger", "Team": "SFG", "HR": 15, "RBI": 48, "SB": 2, "WAR": 2.4},
        {"Player": "Yankees Slugger", "Team": "NYY", "HR": 31, "RBI": 88, "SB": 5, "WAR": 5.0},
        {"Player": "Mets Slugger", "Team": "NYM", "HR": 28, "RBI": 79, "SB": 1, "WAR": 4.3},
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(data).to_excel(writer, sheet_name="2026 MLB Statistics", index=False)
    return path


def write_f1_schedule_minimal(path: Path) -> Path:
    """Minimal F1 Schedule workbook matching ``f1__event-source__f1_schedule.yaml`` columns."""

    rows = [
        {
            "event_id": "FXTEST001",
            "category": "F1",
            "league": "Formula 1",
            "event_name": "Integration GP - Qualifying",
            "event_date": "2026-06-01 10:00:00",
            "home_participant": "drivers",
            "away_participant": "drivers",
            "resolution_source": "FIA Official Results",
            "day_of_week": "",
            "local_time": "",
            "location": "",
            "session_type": "Qualifying",
        },
        {
            "event_id": "FXTEST002",
            "category": "F1",
            "league": "Formula 1",
            "event_name": "Integration GP - Race",
            "event_date": "2026-06-01 14:00:00",
            "home_participant": "drivers",
            "away_participant": "drivers",
            "resolution_source": "FIA Official Results",
            "day_of_week": "",
            "local_time": "",
            "location": "",
            "session_type": "Race",
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="F1 Schedule", index=False)
    return path
