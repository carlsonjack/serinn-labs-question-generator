"""Helpers for parsing uploaded template files."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any


def parse_uploaded_template_file(name: str, raw_bytes: bytes | str) -> list[dict[str, Any]]:
    """Return one or more template dicts from an uploaded JSON or CSV file."""

    suffix = Path(name or "").suffix.lower()
    if isinstance(raw_bytes, bytes):
        text = raw_bytes.decode("utf-8-sig")
    else:
        text = raw_bytes

    if suffix == ".json":
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Root JSON value must be an object")
        return [data]

    if suffix == ".csv":
        return parse_template_csv_blocks(text)

    raise ValueError("Only .json and .csv template files are accepted.")


def parse_template_csv_blocks(text: str) -> list[dict[str, Any]]:
    """Parse repeated 2-row CSV blocks into template dicts."""

    rows = [
        row
        for row in csv.reader(io.StringIO(text))
        if any(str(cell).strip() for cell in row)
    ]
    if not rows:
        raise ValueError("CSV file is empty.")
    if len(rows) % 2 != 0:
        raise ValueError(
            "CSV file must contain header/value row pairs (an even number of non-empty rows)."
        )

    templates: list[dict[str, Any]] = []
    for idx in range(0, len(rows), 2):
        headers = rows[idx]
        values = rows[idx + 1]
        block_num = idx // 2 + 1
        if len(headers) != len(values):
            raise ValueError(
                f"CSV block {block_num} has {len(headers)} header cells but {len(values)} value cells."
            )
        data: dict[str, Any] = {}
        seen_headers: set[str] = set()
        for col_idx, (raw_key, raw_value) in enumerate(zip(headers, values), start=1):
            key = str(raw_key).strip()
            if not key:
                raise ValueError(
                    f"CSV block {block_num} has an empty field name in column {col_idx}."
                )
            if key in seen_headers:
                raise ValueError(
                    f"CSV block {block_num} repeats field {key!r}."
                )
            seen_headers.add(key)
            coerced = _coerce_csv_value(key, raw_value)
            if coerced is _SKIP_FIELD:
                continue
            data[key] = coerced
        if not data:
            raise ValueError(f"CSV block {block_num} is empty.")
        templates.append(data)
    return templates


_SKIP_FIELD = object()


def _coerce_csv_value(key: str, value: Any) -> Any:
    raw = str(value).strip()
    if raw == "":
        if key in {"line", "top_n_per_team", "stat_column", "_comment"}:
            return _SKIP_FIELD
        return ""
    if key == "requires_entities":
        return _parse_bool(raw, key)
    if key == "top_n_per_team":
        return _parse_int(raw, key)
    if key == "line":
        return _parse_float(raw, key)
    if key == "priority":
        return raw.lower()
    return raw


def _parse_bool(raw: str, key: str) -> bool:
    value = raw.strip().lower()
    if value in {"true", "1", "yes", "y"}:
        return True
    if value in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"{key} must be a boolean value.")


def _parse_int(raw: str, key: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer value.") from exc


def _parse_float(raw: str, key: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be a numeric value.") from exc
