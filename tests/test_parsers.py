from __future__ import annotations

from pathlib import Path

from core.config import load_settings
from core.parsers.contracts import SourceRole
from core.parsers.detector import inspect_file
from core.parsers.mlb.schedule import MlbScheduleParser
from core.parsers.mlb.stats import MlbStatsParser
from core.parsers.profiles import load_profiles, save_profile
from core.parsers.service import load_normalized_bundle

ROOT = Path(__file__).resolve().parent.parent
INPUTS = ROOT / "inputs"


def test_schedule_parser_normalizes_events() -> None:
    settings = load_settings()
    result = MlbScheduleParser(settings).load(INPUTS / "schedule.xlsx").normalize()

    assert not result.errors
    assert len(result.data) == 244
    assert result.data[0].event_id == "MLB000657"
    assert result.data[0].event_datetime == "2026-05-15T21:40:00"
    assert result.data[0].home_team == "Athletics"
    assert result.data[0].away_team == "Giants"


def test_stats_parser_handles_malformed_workbook_and_ranks_players() -> None:
    parser = MlbStatsParser().load(INPUTS / "stats.xlsx")
    result = parser.normalize()

    assert not result.errors
    assert len(result.data) == 249
    assert [player.player_name for player in parser.get_top_players("Athletics", "HR", 3)] == [
        "Shea Langeliers",
        "Brent Rooker",
        "Max Muncy",
    ]


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

    assert len(bundle.events) == 244
    assert len(bundle.player_stats) == 249
    assert bundle.issues == []
    assert len(load_profiles("mlb")) == 2

