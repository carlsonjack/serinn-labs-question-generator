"""Question template records loaded from JSON (EPIC 3)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "subcategory",
        "question_family",
        "question",
        "answer_type",
        "answer_options",
        "priority",
        "requires_entities",
        "stat_column",
        "top_n_per_team",
        "line",
        "timeframe",
        "template_name",
        "notes",
        "_comment",
    }
)

QUESTION_FAMILIES: frozenset[str] = frozenset({"event", "entity_stat", "stock"})
ANSWER_TYPES: frozenset[str] = frozenset({"yes_no", "multiple_choice"})


@dataclass(frozen=True)
class QuestionTemplate:
    """One row from templates/*.json after validation."""

    id: str
    subcategory: str
    question_family: str
    question: str
    answer_type: str
    answer_options: str
    priority: int | str
    requires_entities: bool
    stat_column: str | None = None
    top_n_per_team: int | None = None
    line: float | None = None
    timeframe: str | None = None
    template_name: str | None = None
    notes: str | None = None
    _comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for tests and downstream JSON-friendly consumers."""

        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None or k == "_comment"}


def parse_template_dict(data: dict[str, Any]) -> QuestionTemplate:
    """Validate raw JSON object and return a QuestionTemplate."""

    unknown = set(data.keys()) - ALLOWED_KEYS
    if unknown:
        raise ValueError(f"Unknown keys: {sorted(unknown)}")

    missing = [k for k in ("id", "subcategory", "question_family", "question", "answer_type", "priority") if k not in data]
    if missing:
        raise ValueError(f"Missing required keys: {missing}")

    if "requires_entities" not in data:
        raise ValueError("Missing required key: requires_entities")

    qid = _str_field(data, "id")
    subcategory = _str_field(data, "subcategory")
    question_family = _str_field(data, "question_family")
    question = _str_field(data, "question")
    answer_type = _str_field(data, "answer_type")
    priority = _priority_field(data, "priority")

    if question_family not in QUESTION_FAMILIES:
        raise ValueError(f"Invalid question_family: {question_family!r}")
    if answer_type not in ANSWER_TYPES:
        raise ValueError(f"Invalid answer_type: {answer_type!r}")
    requires_entities = data["requires_entities"]
    if not isinstance(requires_entities, bool):
        raise ValueError("requires_entities must be a boolean")

    answer_options = _optional_str_field(data, "answer_options")

    stat_column = data.get("stat_column")
    top_raw = data.get("top_n_per_team")
    line_raw = data.get("line")
    timeframe = data.get("timeframe")
    template_name = data.get("template_name")
    notes = data.get("notes")
    comment = data.get("_comment")

    if stat_column is not None and not isinstance(stat_column, str):
        raise ValueError("stat_column must be a string or omitted")
    if top_raw is not None:
        if isinstance(top_raw, bool) or not isinstance(top_raw, (int, float)):
            raise ValueError("top_n_per_team must be an integer or omitted")
        if isinstance(top_raw, float) and not top_raw.is_integer():
            raise ValueError("top_n_per_team must be a whole number")
    if line_raw is not None and not isinstance(line_raw, (int, float)):
        raise ValueError("line must be a number or omitted")
    if comment is not None and not isinstance(comment, str):
        raise ValueError("_comment must be a string or omitted")
    if timeframe is not None and not isinstance(timeframe, str):
        raise ValueError("timeframe must be a string or omitted")
    if template_name is not None and not isinstance(template_name, str):
        raise ValueError("template_name must be a string or omitted")
    if notes is not None and not isinstance(notes, str):
        raise ValueError("notes must be a string or omitted")

    line: float | None = float(line_raw) if line_raw is not None else None

    if question_family == "entity_stat":
        if line_raw is not None:
            raise ValueError("entity_stat templates must not set line")
        if not requires_entities:
            raise ValueError("entity_stat templates must set requires_entities to true")
        if not stat_column or not stat_column.strip():
            raise ValueError("entity_stat templates require stat_column")
        if top_raw is None or int(top_raw) < 1:
            raise ValueError("entity_stat templates require top_n_per_team >= 1")
        top_n = int(top_raw)
    elif question_family == "event":
        if requires_entities:
            raise ValueError("event templates must set requires_entities to false")
        if stat_column is not None or top_raw is not None:
            raise ValueError("event templates must not set stat_column or top_n_per_team")
        top_n = None
    else:
        if requires_entities:
            raise ValueError("stock templates must set requires_entities to false")
        if stat_column is not None or top_raw is not None:
            raise ValueError("stock templates must not set stat_column or top_n_per_team")
        top_n = None

    _validate_answer_options(answer_type, answer_options, requires_entities, question_family)

    return QuestionTemplate(
        id=qid,
        subcategory=subcategory,
        question_family=question_family,
        question=question,
        answer_type=answer_type,
        answer_options=answer_options,
        priority=priority,
        requires_entities=requires_entities,
        stat_column=stat_column.strip() if stat_column else None,
        top_n_per_team=top_n,
        line=line,
        timeframe=timeframe.strip() if timeframe else None,
        template_name=template_name.strip() if template_name else None,
        notes=notes.strip() if notes else None,
        _comment=comment,
    )


def _str_field(data: dict[str, Any], key: str) -> str:
    if key not in data:
        raise ValueError(f"Missing required key: {key}")
    val = data[key]
    if not isinstance(val, str):
        raise ValueError(f"{key} must be a string")
    if not val.strip():
        raise ValueError(f"{key} must be non-empty")
    return val


def _optional_str_field(data: dict[str, Any], key: str) -> str:
    if key not in data:
        raise ValueError(f"Missing required key: {key}")
    val = data[key]
    if not isinstance(val, str):
        raise ValueError(f"{key} must be a string")
    return val.strip()


def _priority_field(data: dict[str, Any], key: str) -> int | str:
    if key not in data:
        raise ValueError(f"Missing required key: {key}")
    val = data[key]
    if val == "":
        return ""
    if isinstance(val, bool):
        raise ValueError("priority must be an integer or blank")
    if isinstance(val, int):
        if val < 0:
            raise ValueError("priority must be a non-negative integer or blank")
        return val
    raise ValueError("priority must be an integer or blank")


def _validate_answer_options(
    answer_type: str,
    answer_options: str,
    requires_entities: bool,
    question_family: str,
) -> None:
    if answer_type == "yes_no":
        if question_family == "stock" and answer_options == "":
            return
        if answer_options != "Yes||No":
            raise ValueError("yes_no templates must use answer_options: \"Yes||No\"")
        return
    if answer_type == "multiple_choice":
        if requires_entities:
            return
        if "||" not in answer_options:
            raise ValueError("multiple_choice event templates must use || in answer_options")
        return
    raise AssertionError("unreachable")
