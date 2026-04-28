from __future__ import annotations

from pathlib import Path
import shutil

import pandas as pd

from core.config import load_settings
from core.parsers.contracts import SourceRole, ValidationSeverity
from core.parsers.detector import inspect_file
from core.parsers.mlb.schedule import MlbScheduleParser
from core.parsers.mlb.stats import MlbStatsParser
from core.parsers.profiles import load_profiles, save_profile
from core.parsers.season_merge import merge_metric_detection
from core.parsers.service import load_normalized_bundle

ROOT = Path(__file__).resolve().parent.parent
INPUTS = ROOT / "inputs"


def test_schedule_parser_normalizes_events() -> None:
    settings = load_settings()
    result = MlbScheduleParser(settings).load(INPUTS / "schedule.xlsx").normalize()

    assert not result.errors
    assert result.data
    assert result.data[0].event_id == "MLB000657"
    assert result.data[0].event_datetime == "2026-05-15T21:40:00"
    assert result.data[0].home_team == "Athletics"
    assert result.data[0].away_team == "Giants"


def test_stats_parser_handles_malformed_workbook_and_ranks_players() -> None:
    parser = MlbStatsParser().load(INPUTS / "stats.xlsx")
    result = parser.normalize()

    assert not result.errors
    assert result.data
    assert [player.player_name for player in parser.get_top_players("Athletics", "HR", 3)] == [
        "Nick Kurtz*",
        "Shea Langeliers",
        "Brent Rooker",
    ]
    assert result.data[0].source_sheet == "2025 MLB Statistics -> 2026 MLB Statistics"


def test_saved_profile_is_reused_for_repeat_detection(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("core.parsers.profiles._PROFILE_DIR", tmp_path / "profiles")

    first_detection = inspect_file(
        INPUTS / "schedule.xlsx",
        category_key="mlb",
        preferred_role=SourceRole.EVENT_SOURCE,
    )
    profile = first_detection.detected_file.profile_used
    profile.normalizer_options = {"saved": True}
    save_profile(profile)

    second_detection = inspect_file(
        INPUTS / "schedule.xlsx",
        category_key="mlb",
        preferred_role=SourceRole.EVENT_SOURCE,
    )

    assert load_profiles("mlb")
    assert second_detection.detected_file.profile_used.normalizer_options == {"saved": True}


def test_schedule_parser_reports_missing_required_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad_schedule.csv"
    csv_path.write_text("event_id,home_team\nMLB1,Athletics\n", encoding="utf-8")

    result = MlbScheduleParser(load_settings()).load(csv_path).normalize()

    assert result.errors
    assert {issue.field_name for issue in result.errors} >= {
        "event_date",
        "event_time",
        "away_team",
    }


def test_load_normalized_bundle_persists_profiles_and_has_no_issues(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("core.parsers.profiles._PROFILE_DIR", tmp_path / "profiles")
    settings = load_settings()
    settings["inputs"]["directory"] = str(INPUTS)

    bundle = load_normalized_bundle(settings)

    assert bundle.events
    assert bundle.player_stats
    assert not any(issue.severity == ValidationSeverity.ERROR for issue in bundle.issues)
    assert len(load_profiles("mlb")) == 2


def test_metric_workbook_merges_prior_year_stats_with_current_team_by_player_id(
    tmp_path: Path,
) -> None:
    workbook = _write_stats_workbook(
        tmp_path / "seasonal_stats.xlsx",
        stats_rows=[
            {
                "Player ID": "101",
                "Player": "Slugger Sam",
                "Team": "OAK",
                "HR": 31,
                "RBI": 87,
                "SB": 6,
                "WAR": 4.1,
            }
        ],
        association_rows=[
            {
                "Player ID": "101",
                "Player": "Slugger Sam",
                "Team": "NYY",
                "HR": 2,
                "RBI": 5,
                "SB": 0,
                "WAR": 0.4,
            }
        ],
    )

    detection = inspect_file(
        workbook,
        category_key="mlb",
        preferred_role=SourceRole.METRIC_SOURCE,
        preferred_sheet_terms=("2026",),
    )
    merge_result = merge_metric_detection(detection)
    parsed = MlbStatsParser().load(workbook).normalize()

    assert detection.detected_file.sheet_name == "2026 MLB Statistics"
    assert merge_result.used_multi_sheet is True
    assert merge_result.stats_sheet.sheet_name == "2025 MLB Statistics"
    assert merge_result.association_sheet is not None
    assert merge_result.association_sheet.sheet_name == "2026 MLB Statistics"
    assert merge_result.join_strategy == "player_id"
    assert not parsed.errors
    assert parsed.data[0].team == "NYY"
    assert parsed.data[0].stat_values["HR"] == 31.0
    assert parsed.data[0].source_sheet == "2025 MLB Statistics -> 2026 MLB Statistics"


def test_metric_workbook_falls_back_to_name_matching_when_ids_absent(tmp_path: Path) -> None:
    workbook = _write_stats_workbook(
        tmp_path / "name_only_stats.xlsx",
        stats_rows=[
            {"Player": "Fast Runner", "Team": "ATH", "HR": 5, "RBI": 40, "SB": 32, "WAR": 2.8}
        ],
        association_rows=[
            {"Player": "Fast Runner", "Team": "SEA", "HR": 1, "RBI": 3, "SB": 2, "WAR": 0.2}
        ],
        include_ids=False,
    )

    parsed = MlbStatsParser().load(workbook).normalize()

    assert not parsed.errors
    assert parsed.data[0].team == "SEA"
    assert parsed.data[0].stat_values["SB"] == 32.0


def test_metric_workbook_warns_on_ambiguous_name_match_and_keeps_historical_team(
    tmp_path: Path,
) -> None:
    workbook = _write_stats_workbook(
        tmp_path / "ambiguous_stats.xlsx",
        stats_rows=[
            {"Player": "Alex Smith", "Team": "ATH", "HR": 10, "RBI": 55, "SB": 7, "WAR": 2.0}
        ],
        association_rows=[
            {"Player": "Alex Smith", "Team": "SEA", "HR": 1, "RBI": 1, "SB": 1, "WAR": 0.1},
            {"Player": "Alex Smith", "Team": "NYY", "HR": 2, "RBI": 2, "SB": 2, "WAR": 0.2},
        ],
        include_ids=False,
    )

    parsed = MlbStatsParser().load(workbook).normalize()

    assert not parsed.errors
    assert parsed.data[0].team == "ATH"
    assert any(issue.code == "season_merge_ambiguous_player" for issue in parsed.warnings)


def test_single_sheet_metric_workbook_still_parses_without_merge(tmp_path: Path) -> None:
    workbook = tmp_path / "single_sheet_stats.xlsx"
    with pd.ExcelWriter(workbook) as writer:
        pd.DataFrame(
            [
                {
                    "Player": "Solo Bat",
                    "Team": "LAD",
                    "HR": 21,
                    "RBI": 61,
                    "SB": 4,
                    "WAR": 3.0,
                }
            ]
        ).to_excel(writer, index=False, sheet_name="2026 MLB Statistics")

    parsed = MlbStatsParser().load(workbook).normalize()

    assert not parsed.errors
    assert parsed.data[0].team == "LAD"
    assert parsed.data[0].source_sheet == "2026 MLB Statistics"


def test_load_normalized_bundle_persists_merge_heuristics_in_metric_profile(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("core.parsers.profiles._PROFILE_DIR", tmp_path / "profiles")
    shutil.copyfile(INPUTS / "schedule.xlsx", tmp_path / "schedule.xlsx")
    _write_stats_workbook(
        tmp_path / "stats.xlsx",
        stats_rows=[
            {
                "Player ID": "101",
                "Player": "Slugger Sam",
                "Team": "ATH",
                "HR": 31,
                "RBI": 87,
                "SB": 6,
                "WAR": 4.1,
            }
        ],
        association_rows=[
            {
                "Player ID": "101",
                "Player": "Slugger Sam",
                "Team": "NYY",
                "HR": 2,
                "RBI": 5,
                "SB": 0,
                "WAR": 0.4,
            }
        ],
    )
    settings = load_settings()
    settings["inputs"]["directory"] = str(tmp_path)

    bundle = load_normalized_bundle(settings)
    metric_profile = next(
        profile for profile in load_profiles("mlb") if profile.source_role == SourceRole.METRIC_SOURCE
    )

    assert bundle.player_stats
    assert metric_profile.normalizer_options["stats_sheet_name"] == "2025 MLB Statistics"
    assert metric_profile.normalizer_options["association_sheet_name"] == "2026 MLB Statistics"
    assert metric_profile.normalizer_options["join_strategy"] == "player_id"


def _write_stats_workbook(
    path: Path,
    *,
    stats_rows: list[dict[str, object]],
    association_rows: list[dict[str, object]],
    include_ids: bool = True,
) -> Path:
    stats_frame = pd.DataFrame(stats_rows)
    association_frame = pd.DataFrame(association_rows)
    if not include_ids:
        stats_frame = stats_frame.drop(columns=["Player ID"], errors="ignore")
        association_frame = association_frame.drop(columns=["Player ID"], errors="ignore")
    with pd.ExcelWriter(path) as writer:
        stats_frame.to_excel(writer, index=False, sheet_name="2025 MLB Statistics")
        association_frame.to_excel(writer, index=False, sheet_name="2026 MLB Statistics")
    return path

