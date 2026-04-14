"""Detect file structure, source role, and field mappings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Any, Iterable

import pandas as pd

from .contracts import DetectedFile, InputProfile, SourceRole, ValidationIssue, ValidationSeverity
from .profiles import fingerprint_file, match_profile

_XML_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_HEADER_SCAN_LIMIT = 10
FIELD_ALIASES: dict[str, set[str]] = {
    "event_id": {"event id", "event_id", "game id", "id"},
    "event_name": {"event name", "event_name", "matchup", "event"},
    "event_date": {"event date", "event_date", "date", "game date"},
    "event_time": {"event time", "event_time", "time", "start time"},
    "home_team": {"home team", "home_team", "home"},
    "away_team": {"away team", "away_team", "away"},
    "player_name": {"player", "player name", "name", "batter"},
    "team": {"team", "club"},
    "league": {"lg", "league"},
    "war": {"war"},
    "hr": {"hr", "home runs"},
    "rbi": {"rbi"},
    "sb": {"sb", "stolen bases"},
}


@dataclass
class DetectionResult:
    """Detector return type with structured issues."""

    detected_file: DetectedFile
    issues: list[ValidationIssue]


def _normalize_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"[^a-z0-9 ]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _column_letter(cell_ref: str) -> str:
    chars: list[str] = []
    for ch in cell_ref:
        if ch.isalpha():
            chars.append(ch)
        else:
            break
    return "".join(chars)


def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall("a:si", _XML_NS):
        parts = [node.text or "" for node in item.findall(".//a:t", _XML_NS)]
        strings.append("".join(parts))
    return strings


def _sheet_xml_targets(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        rel.attrib["Id"]: f"xl/{rel.attrib['Target']}" for rel in rels if rel.attrib["Type"].endswith("/worksheet")
    }
    targets: list[tuple[str, str]] = []
    for sheet in workbook.findall("a:sheets/a:sheet", _XML_NS):
        relation_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        targets.append((sheet.attrib["name"], rel_map[relation_id]))
    return targets


def _read_raw_xlsx(path: Path) -> dict[str, list[list[str]]]:
    workbook_data: dict[str, list[list[str]]] = {}
    with zipfile.ZipFile(path) as zf:
        strings = _shared_strings(zf)
        for sheet_name, xml_path in _sheet_xml_targets(zf):
            root = ET.fromstring(zf.read(xml_path))
            rows: list[list[str]] = []
            for row in root.findall("a:sheetData/a:row", _XML_NS):
                values_by_column: dict[str, str] = {}
                max_col_index = 0
                for cell in row.findall("a:c", _XML_NS):
                    ref = cell.attrib.get("r", "")
                    column = _column_letter(ref)
                    if not column:
                        continue
                    col_index = 0
                    for letter in column:
                        col_index = (col_index * 26) + (ord(letter.upper()) - 64)
                    max_col_index = max(max_col_index, col_index)
                    cell_type = cell.attrib.get("t")
                    value_node = cell.find("a:v", _XML_NS)
                    value = value_node.text if value_node is not None else ""
                    if cell_type == "s" and value:
                        value = strings[int(value)]
                    values_by_column[column] = value
                if max_col_index == 0:
                    continue
                rows.append(
                    [values_by_column.get(_index_to_column(i), "") for i in range(1, max_col_index + 1)]
                )
            workbook_data[sheet_name] = rows
    return workbook_data


def _index_to_column(index: int) -> str:
    chars: list[str] = []
    while index > 0:
        index, rem = divmod(index - 1, 26)
        chars.append(chr(65 + rem))
    return "".join(reversed(chars))


def _rows_to_frame(rows: list[list[Any]]) -> pd.DataFrame:
    width = max((len(row) for row in rows), default=0)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    return pd.DataFrame(normalized)


def _read_workbook_sheets(path: Path) -> dict[str, pd.DataFrame]:
    if path.suffix.lower() == ".csv":
        return {path.stem: pd.read_csv(path, header=None)}
    try:
        excel = pd.ExcelFile(path)
        return {
            sheet_name: excel.parse(sheet_name, header=None)
            for sheet_name in excel.sheet_names
        }
    except Exception:
        raw_sheets = _read_raw_xlsx(path)
        return {
            sheet_name: _rows_to_frame(rows)
            for sheet_name, rows in raw_sheets.items()
        }


def _header_score(row: Iterable[Any]) -> float:
    labels = [_normalize_label(value) for value in row]
    non_empty = [label for label in labels if label]
    if not non_empty:
        return 0.0
    alias_hits = sum(
        1
        for label in non_empty
        if any(label in aliases for aliases in FIELD_ALIASES.values())
    )
    uniqueness_bonus = len(set(non_empty)) / max(len(non_empty), 1)
    return alias_hits + uniqueness_bonus


def _detect_header_row(frame: pd.DataFrame) -> int:
    limit = min(len(frame.index), _HEADER_SCAN_LIMIT)
    best_index = 0
    best_score = -1.0
    for index in range(limit):
        score = _header_score(frame.iloc[index].tolist())
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


def _canonical_field_mappings(columns: list[str]) -> dict[str, str]:
    mappings: dict[str, str] = {}
    for column in columns:
        normalized = _normalize_label(column)
        for canonical_field, aliases in FIELD_ALIASES.items():
            if normalized in aliases:
                mappings[canonical_field] = column
    return mappings


def _infer_source_role(mappings: dict[str, str]) -> SourceRole:
    if {"event_date", "home_team", "away_team"} <= mappings.keys():
        return SourceRole.EVENT_SOURCE
    if {"player_name", "team"} <= mappings.keys():
        return SourceRole.METRIC_SOURCE
    if "team" in mappings:
        return SourceRole.ENTITY_SOURCE
    return SourceRole.UNKNOWN


def _build_records(frame: pd.DataFrame, header_row_index: int) -> tuple[list[str], list[dict[str, Any]]]:
    header_values = [str(value).strip() for value in frame.iloc[header_row_index].tolist()]
    data_frame = frame.iloc[header_row_index + 1 :].copy()
    data_frame.columns = header_values
    data_frame = data_frame.dropna(how="all").fillna("")
    columns = [column for column in header_values if column]
    if columns:
        data_frame = data_frame.loc[:, columns]
    return columns, data_frame.to_dict(orient="records")


def inspect_file(
    filepath: str | Path,
    *,
    category_key: str,
    preferred_role: SourceRole | None = None,
    preferred_sheet_terms: tuple[str, ...] = (),
) -> DetectionResult:
    """Inspect one file and infer a reusable parse profile."""

    path = Path(filepath)
    profile = match_profile(path, category_key=category_key, source_role=preferred_role)
    issues: list[ValidationIssue] = []
    sheets = _read_workbook_sheets(path)
    sheet_order = list(sheets)
    chosen_sheet_name = sheet_order[0] if sheet_order else None
    if preferred_sheet_terms:
        lowered_terms = tuple(term.lower() for term in preferred_sheet_terms)
        for sheet_name in sheet_order:
            if any(term in sheet_name.lower() for term in lowered_terms):
                chosen_sheet_name = sheet_name
                break
    if profile and profile.sheet_name in sheets:
        chosen_sheet_name = profile.sheet_name

    if chosen_sheet_name is None:
        raise FileNotFoundError(f"No readable sheets found in {path}")

    frame = sheets[chosen_sheet_name]
    header_row_index = profile.header_row_index if profile else _detect_header_row(frame)
    columns, records = _build_records(frame, header_row_index)
    field_mappings = profile.field_mappings if profile else _canonical_field_mappings(columns)
    source_role = preferred_role or (profile.source_role if profile else _infer_source_role(field_mappings))

    confidence = min(
        1.0,
        (len(field_mappings) / max(len(columns), 1)) + (0.25 if source_role != SourceRole.UNKNOWN else 0.0),
    )

    if source_role == SourceRole.UNKNOWN:
        issues.append(
            ValidationIssue(
                code="unknown_source_role",
                message=f"Could not confidently classify {path.name}.",
                severity=ValidationSeverity.WARNING,
                file_path=str(path),
            )
        )

    detected = DetectedFile(
        file_path=path,
        format_name=path.suffix.lower().lstrip(".") or "unknown",
        source_role=source_role,
        sheet_name=chosen_sheet_name,
        header_row_index=header_row_index,
        columns=columns,
        field_mappings=field_mappings,
        confidence=confidence,
        records=records,
        profile_used=profile
        or InputProfile(
            profile_name=path.stem,
            category_key=category_key,
            file_pattern=path.name,
            source_role=source_role,
            format_name=path.suffix.lower().lstrip(".") or "unknown",
            sheet_name=chosen_sheet_name,
            header_row_index=header_row_index,
            field_mappings=field_mappings,
            fingerprint=fingerprint_file(path),
            confidence=confidence,
        ),
    )
    return DetectionResult(detected_file=detected, issues=issues)

