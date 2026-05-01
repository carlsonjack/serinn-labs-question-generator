"""Programmatic .xlsx builders for integration tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


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
