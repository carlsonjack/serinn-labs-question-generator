"""Compute question start/expiration/resolution datetimes from event time and YAML rules.

Naive ISO 8601 strings (no timezone offset) are returned. Event times with a Z suffix
are interpreted as UTC and converted to naive UTC for arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

_DEFAULT_START_HOURS = -24
_DEFAULT_EXPIRATION_HOURS = 0
_DEFAULT_RESOLUTION_HOURS = 4


@dataclass(frozen=True)
class QuestionDates:
    start_date: str
    expiration_date: str
    resolution_date: str


def parse_event_datetime(value: str | datetime) -> datetime:
    """Return a naive datetime. Aware inputs are converted to UTC then made naive."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def get_date_rules_for_category(settings: dict[str, Any], category_key: str) -> dict[str, int]:
    """Merge date_rules.default with date_rules[category_key] (category wins)."""
    rules_root = settings.get("date_rules")
    if not isinstance(rules_root, dict):
        rules_root = {}
    default = rules_root.get("default")
    if not isinstance(default, dict):
        default = {}
    merged: dict[str, Any] = dict(default)
    cat = rules_root.get(category_key)
    if isinstance(cat, dict):
        merged.update(cat)
    return {
        "start_offset_hours": int(merged.get("start_offset_hours", _DEFAULT_START_HOURS)),
        "expiration_offset_hours": int(
            merged.get("expiration_offset_hours", _DEFAULT_EXPIRATION_HOURS)
        ),
        "resolution_offset_hours": int(
            merged.get("resolution_offset_hours", _DEFAULT_RESOLUTION_HOURS)
        ),
    }


def _format_iso_naive(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def compute_question_dates(
    event_datetime: str | datetime,
    *,
    category_key: str,
    settings: dict[str, Any] | None = None,
) -> QuestionDates:
    """Apply category date rules to event_datetime; all values are naive ISO strings."""
    cfg = settings if settings is not None else {}
    r = get_date_rules_for_category(cfg, category_key)
    base = parse_event_datetime(event_datetime)
    start = base + timedelta(hours=r["start_offset_hours"])
    expiration = base + timedelta(hours=r["expiration_offset_hours"])
    resolution = base + timedelta(hours=r["resolution_offset_hours"])
    return QuestionDates(
        start_date=_format_iso_naive(start),
        expiration_date=_format_iso_naive(expiration),
        resolution_date=_format_iso_naive(resolution),
    )
