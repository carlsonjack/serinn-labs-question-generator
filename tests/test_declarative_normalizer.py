"""Declarative normalizer profile execution and AI proposal helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.parsers.ai_profile_builder import propose_normalization_spec
from core.parsers.contracts import (
    EventDatetimeSpec,
    EventIdSpec,
    MatchupSplitSpec,
    NormalizationSpec,
    SourceNormalizationSpec,
    SourceRole,
    ValidationSeverity,
)
from core.parsers.declarative import execute_normalization_spec
from core.parsers.detector import inspect_file
from core.parsers.profiles import save_normalization_spec
from core.parsers.service import load_normalized_bundle


def _write_world_cup_schedule(path: Path) -> Path:
    rows = [
        {
            "Date": "11-Jun-26",
            "Time (EST)": "15:00",
            "Time (Local)": "13:00",
            "Matchup": "Mexico v South Africa",
            "Group": "A",
            "Venue": "Estadio Azteca",
            "City": "Mexico City",
        }
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def _write_world_cup_stats(path: Path) -> Path:
    rows = [
        {
            "Group": "A",
            "Team": "Mexico",
            "Player": "Santiago Gimenez",
            "Archetype": "Primary Scorer",
            "Goal Probability": 0.65,
            "Assist Probability": 0.2,
            "Star Power": "High",
        }
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def _write_stock_watchlist(path: Path) -> Path:
    rows = [
        {
            "Topic Import ID": "stocks-us-market",
            "Company Name": "Apple Inc.",
            "Ticker": "AAPL",
            "topic_name": "US Stock Market",
        }
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def _world_cup_spec() -> NormalizationSpec:
    return NormalizationSpec(
        package_key="WorldCup",
        sources={
            "event_source": SourceNormalizationSpec(
                source_role=SourceRole.EVENT_SOURCE,
                file_pattern="schedule.xlsx",
                field_mappings={
                    "event_date": "Date",
                    "event_time": "Time (EST)",
                    "event_display": "Matchup",
                },
                metadata_mappings={
                    "group": "Group",
                    "venue": "Venue",
                    "city": "City",
                },
                matchup_split=MatchupSplitSpec(
                    source_column="Matchup",
                    delimiter_pattern=r"\s+v\s+",
                ),
                event_datetime=EventDatetimeSpec(
                    date_column="Date",
                    time_column="Time (EST)",
                    timezone="America/New_York",
                ),
                event_id=EventIdSpec(source_columns=["Date", "Matchup"]),
            ),
            "metric_source": SourceNormalizationSpec(
                source_role=SourceRole.METRIC_SOURCE,
                file_pattern="stats.xlsx",
                field_mappings={"player_name": "Player", "team": "Team"},
                metric_mappings={
                    "GOAL_PROBABILITY": "Goal Probability",
                    "ASSIST_PROBABILITY": "Assist Probability",
                },
                metadata_mappings={
                    "group": "Group",
                    "archetype": "Archetype",
                    "star_power": "Star Power",
                },
            ),
        },
    )


def test_declarative_world_cup_schedule_and_probability_stats(tmp_path: Path) -> None:
    schedule = _write_world_cup_schedule(tmp_path / "schedule.xlsx")
    stats = _write_world_cup_stats(tmp_path / "stats.xlsx")
    detected = [
        inspect_file(
            schedule,
            category_key="world_cup",
            preferred_role=SourceRole.EVENT_SOURCE,
        ).detected_file,
        inspect_file(
            stats,
            category_key="world_cup",
            preferred_role=SourceRole.METRIC_SOURCE,
        ).detected_file,
    ]

    bundle = execute_normalization_spec(
        _world_cup_spec(),
        detected,
        {"date_filter": {"start": "2026-01-01", "end": "2026-12-31"}},
    )
    errors = [i for i in bundle.issues if i.severity == ValidationSeverity.ERROR]
    assert not errors
    assert bundle.events[0].home_team == "Mexico"
    assert bundle.events[0].away_team == "South Africa"
    assert bundle.events[0].metadata["venue"] == "Estadio Azteca"
    assert bundle.player_stats[0].player_name == "Santiago Gimenez"
    assert bundle.player_stats[0].stat_values["GOAL_PROBABILITY"] == 0.65
    assert bundle.player_stats[0].metadata["star_power"] == "High"


def test_declarative_event_datetime_accepts_natural_language_without_year(
    tmp_path: Path,
) -> None:
    schedule = tmp_path / "schedule.xlsx"
    pd.DataFrame(
        [
            {
                "When": "Saturday, November 7 7 pm",
                "Matchup": "Mexico v South Africa",
            }
        ]
    ).to_excel(schedule, index=False)
    detected = [
        inspect_file(
            schedule,
            category_key="world_cup",
            preferred_role=SourceRole.EVENT_SOURCE,
        ).detected_file
    ]
    spec = NormalizationSpec(
        package_key="WorldCup",
        sources={
            "event_source": SourceNormalizationSpec(
                source_role=SourceRole.EVENT_SOURCE,
                file_pattern="schedule.xlsx",
                field_mappings={"event_datetime": "When"},
                matchup_split=MatchupSplitSpec(
                    source_column="Matchup",
                    delimiter_pattern=r"\s+v\s+",
                ),
                event_id=EventIdSpec(source_columns=["When", "Matchup"]),
            )
        },
    )

    bundle = execute_normalization_spec(
        spec,
        detected,
        {"date_filter": {"start": "2026-01-01", "end": "2026-12-31"}},
    )

    errors = [i for i in bundle.issues if i.severity == ValidationSeverity.ERROR]
    assert not errors
    assert bundle.events[0].event_datetime == "2026-11-07T19:00:00"


def test_ai_profile_heuristic_maps_world_cup_layout(tmp_path: Path) -> None:
    _write_world_cup_schedule(tmp_path / "schedule.xlsx")
    _write_world_cup_stats(tmp_path / "stats.xlsx")
    spec, snapshots = propose_normalization_spec(
        {},
        category_key="WorldCup",
        input_dir=tmp_path,
        file_config={
            "event_source": "schedule.xlsx",
            "metric_source": "stats.xlsx",
        },
        use_ai=False,
    )
    assert snapshots
    event_source = spec.sources["event_source"]
    metric_source = spec.sources["metric_source"]
    assert event_source.matchup_split is not None
    assert event_source.matchup_split.source_column == "Matchup"
    assert metric_source.field_mappings["player_name"] == "Player"
    assert metric_source.metric_mappings["GOAL_PROBABILITY"] == "Goal Probability"
    assert metric_source.metadata_mappings["star_power"] == "Star Power"


def test_stocks_profile_can_be_entity_source_only(tmp_path: Path) -> None:
    watchlist = _write_stock_watchlist(tmp_path / "top-150-stocks.xlsx")
    detected = [
        inspect_file(
            watchlist,
            category_key="stocks",
            preferred_role=SourceRole.ENTITY_SOURCE,
        ).detected_file
    ]
    spec = NormalizationSpec(
        package_key="stocks",
        sources={
            "metric_source": SourceNormalizationSpec(
                source_role=SourceRole.ENTITY_SOURCE,
                file_pattern="top-150-stocks.xlsx",
                field_mappings={
                    "company_name": "Company Name",
                    "ticker": "Ticker",
                    "topic_import_id": "Topic Import ID",
                },
                metadata_mappings={"topic_name": "topic_name"},
            )
        },
    )

    bundle = execute_normalization_spec(spec, detected, {})

    errors = [i for i in bundle.issues if i.severity == ValidationSeverity.ERROR]
    assert not errors
    assert bundle.entities[0].entity_id == "AAPL"
    assert bundle.entities[0].display_name == "Apple Inc. (AAPL)"


def test_ai_profile_heuristic_maps_stocks_metric_slot_to_entity_source(tmp_path: Path) -> None:
    _write_stock_watchlist(tmp_path / "top-150-stocks.xlsx")

    spec, snapshots = propose_normalization_spec(
        {
            "inputs": {
                "file_roles": {
                    "stocks": {
                        "metric_source": "entity_source",
                    }
                }
            }
        },
        category_key="stocks",
        input_dir=tmp_path,
        file_config={"metric_source": "top-150-stocks.xlsx"},
        use_ai=True,
    )

    assert snapshots[0]["source_role"] == "entity_source"
    source = spec.sources["metric_source"]
    assert source.source_role == SourceRole.ENTITY_SOURCE
    assert source.field_mappings["company_name"] == "Company Name"
    assert source.field_mappings["ticker"] == "Ticker"


def test_unknown_schedule_only_package_uses_saved_declarative_spec(
    tmp_path: Path, monkeypatch
) -> None:
    profile_root = tmp_path / "profiles"
    monkeypatch.setattr("core.parsers.profiles._PROFILE_DIR", profile_root)
    _write_world_cup_schedule(tmp_path / "schedule.xlsx")

    spec = NormalizationSpec(
        package_key="WorldCup",
        sources={
            "event_source": _world_cup_spec().sources["event_source"],
        },
    )
    save_normalization_spec(spec)

    bundle = load_normalized_bundle(
        {
            "inputs": {
                "directory": str(tmp_path),
                "category_key": "WorldCup",
                "files": {"WorldCup": {"event_source": "schedule.xlsx"}},
            },
            "date_filter": {"start": "2026-01-01", "end": "2026-12-31"},
            "parsing": {"persist_profiles": False},
        },
        category_key="WorldCup",
    )
    errors = [i for i in bundle.issues if i.severity == ValidationSeverity.ERROR]
    assert not errors
    assert bundle.events[0].event_display == "Mexico v South Africa"
