"""Typed contracts for the input parser layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class SourceRole(str, Enum):
    """Cross-vertical roles a source file can play."""

    EVENT_SOURCE = "event_source"
    ENTITY_SOURCE = "entity_source"
    METRIC_SOURCE = "metric_source"
    REFERENCE_SOURCE = "reference_source"
    UNKNOWN = "unknown"


class ValidationSeverity(str, Enum):
    """Severity levels for parser issues."""

    ERROR = "error"
    WARNING = "warning"


@dataclass
class ValidationIssue:
    """A structured issue discovered during detection or normalization."""

    code: str
    message: str
    severity: ValidationSeverity
    file_path: str | None = None
    source_role: SourceRole | None = None
    field_name: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class InputProfile:
    """Persisted detection metadata for reproducible imports."""

    profile_name: str
    category_key: str
    file_pattern: str
    source_role: SourceRole
    format_name: str
    sheet_name: str | None
    header_row_index: int
    field_mappings: dict[str, str]
    fingerprint: str | None = None
    confidence: float | None = None
    normalizer_options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_role"] = self.source_role.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InputProfile":
        return cls(
            profile_name=data["profile_name"],
            category_key=data["category_key"],
            file_pattern=data["file_pattern"],
            source_role=SourceRole(data["source_role"]),
            format_name=data["format_name"],
            sheet_name=data.get("sheet_name"),
            header_row_index=int(data["header_row_index"]),
            field_mappings=dict(data.get("field_mappings", {})),
            fingerprint=data.get("fingerprint"),
            confidence=data.get("confidence"),
            normalizer_options=dict(data.get("normalizer_options", {})),
        )


@dataclass
class DetectedFile:
    """A raw input file after structure detection."""

    file_path: Path
    format_name: str
    source_role: SourceRole
    sheet_name: str | None
    header_row_index: int
    columns: list[str]
    field_mappings: dict[str, str]
    confidence: float
    records: list[dict[str, Any]]
    profile_used: InputProfile | None = None


@dataclass
class NormalizedEvent:
    """Canonical event record consumed by downstream epics."""

    event_id: str
    home_team: str
    away_team: str
    event_datetime: str
    subcategory: str


@dataclass
class PlayerStatRecord:
    """Canonical player metric record for entity-based templates."""

    player_name: str
    team: str
    source_team: str
    stat_values: dict[str, float]
    source_sheet: str | None
    row_number: int


@dataclass
class ParserResult:
    """Standard return envelope for file parsers."""

    data: list[Any]
    warnings: list[ValidationIssue] = field(default_factory=list)
    errors: list[ValidationIssue] = field(default_factory=list)
    profile_used: InputProfile | None = None


@dataclass
class NormalizedBundle:
    """All normalized parser outputs needed by downstream stages."""

    events: list[NormalizedEvent] = field(default_factory=list)
    player_stats: list[PlayerStatRecord] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    profiles: list[InputProfile] = field(default_factory=list)

