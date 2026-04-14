"""Schema validation layer (EPIC 6, Task 6.2).

Validates every output row against the expected CSV schema before final export.
Rows that fail validation are separated and written to ``outputs/errors.csv``
with a human-readable ``reason`` column explaining the failure.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from core.generation.row_assembler import OUTPUT_COLUMNS, OutputRow

logger = logging.getLogger(__name__)

REQUIRED_FIELDS: list[str] = list(OUTPUT_COLUMNS)
"""Every column in the output schema is required (must be non-empty)."""

VALID_ANSWER_TYPES: frozenset[str] = frozenset({"yes_no", "multiple_choice"})
VALID_PRIORITY_FLAGS: frozenset[str] = frozenset({"true", "false"})
DATE_FIELDS: list[str] = ["start_date", "expiration_date", "resolution_date"]


@dataclass
class RowValidationError:
    """A single validation failure for one row."""

    row: OutputRow
    reasons: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Outcome of running schema validation on a batch of rows."""

    valid_rows: list[OutputRow] = field(default_factory=list)
    invalid_rows: list[RowValidationError] = field(default_factory=list)

    @property
    def total_input(self) -> int:
        return len(self.valid_rows) + len(self.invalid_rows)

    @property
    def valid_count(self) -> int:
        return len(self.valid_rows)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid_rows)


def _is_valid_iso8601(value: str) -> bool:
    """Return True if *value* parses as a valid ISO 8601 datetime string."""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    try:
        datetime.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False


def validate_row(row: OutputRow) -> list[str]:
    """Validate a single row and return a list of failure reasons (empty = valid)."""
    reasons: list[str] = []
    row_dict = row.to_dict()

    for col in REQUIRED_FIELDS:
        val = row_dict.get(col, "")
        if val is None or str(val).strip() == "":
            reasons.append(f"Missing required field: {col}")

    if row.answer_type not in VALID_ANSWER_TYPES:
        reasons.append(
            f"Invalid answer_type: {row.answer_type!r} "
            f"(expected one of {sorted(VALID_ANSWER_TYPES)})"
        )

    for date_col in DATE_FIELDS:
        date_val = row_dict.get(date_col, "")
        if date_val and not _is_valid_iso8601(str(date_val)):
            reasons.append(
                f"Invalid ISO 8601 date in {date_col}: {date_val!r}"
            )

    if row.priority_flag not in VALID_PRIORITY_FLAGS:
        reasons.append(
            f"Invalid priority_flag: {row.priority_flag!r} "
            f"(expected one of {sorted(VALID_PRIORITY_FLAGS)})"
        )

    return reasons


def validate_rows(rows: Sequence[OutputRow]) -> ValidationResult:
    """Run schema validation on all rows and partition into valid/invalid.

    Parameters
    ----------
    rows:
        Output rows to validate.

    Returns
    -------
    ValidationResult:
        Contains ``valid_rows`` that passed all checks and ``invalid_rows``
        with attached failure reasons.
    """
    result = ValidationResult()

    for row in rows:
        reasons = validate_row(row)
        if reasons:
            result.invalid_rows.append(RowValidationError(row=row, reasons=reasons))
            logger.debug("Row failed validation: %s", reasons)
        else:
            result.valid_rows.append(row)

    if result.invalid_rows:
        logger.info(
            "Schema validation: %d valid, %d invalid out of %d total",
            result.valid_count,
            result.invalid_count,
            result.total_input,
        )
    else:
        logger.info(
            "Schema validation: all %d rows passed", result.total_input
        )

    return result


def write_errors_csv(
    errors: Sequence[RowValidationError],
    output_path: str | Path = "outputs/errors.csv",
) -> Path:
    """Write invalid rows to a CSV file with a ``reason`` column.

    The CSV contains the standard output columns plus a ``reason`` column
    listing every validation failure for that row (semicolon-separated when
    there are multiple failures).
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = OUTPUT_COLUMNS + ["reason"]

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for error in errors:
            row_dict: dict[str, Any] = error.row.to_dict()
            row_dict["reason"] = "; ".join(error.reasons)
            writer.writerow(row_dict)

    logger.info("Wrote %d error row(s) to %s", len(errors), path)
    return path
