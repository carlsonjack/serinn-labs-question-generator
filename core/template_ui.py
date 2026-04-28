"""UI-facing descriptions, previews, and package matching for templates."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from core.template_config.schema import QuestionTemplate

_PACKAGE_TOKEN_RE = re.compile(r"[^a-z0-9]+")


def normalize_template_package(value: str) -> str:
    """Normalize package/subcategory labels for case-insensitive matching."""

    return _PACKAGE_TOKEN_RE.sub("", (value or "").strip().lower())


def template_matches_package(template: QuestionTemplate, package_key: str) -> bool:
    """Whether ``template`` belongs to ``package_key`` under normalized matching."""

    pkg = normalize_template_package(package_key)
    if not pkg:
        return False
    return normalize_template_package(template.subcategory) == pkg


def filter_templates_for_package(
    templates: Iterable[QuestionTemplate], package_key: str
) -> list[QuestionTemplate]:
    """Return templates whose subcategory matches the selected input package."""

    return sorted(
        [t for t in templates if template_matches_package(t, package_key)],
        key=lambda t: t.id,
    )


def infer_subcategory_for_package(
    templates: Iterable[QuestionTemplate], package_key: str, fallback: str = ""
) -> str:
    """Return the UI/display subcategory label for the selected package."""

    matched = filter_templates_for_package(templates, package_key)
    if matched:
        return matched[0].subcategory
    raw = (fallback or "").strip()
    if raw:
        return raw
    pkg = (package_key or "").strip()
    if not pkg:
        return "MLB"
    if "_" in pkg or "-" in pkg:
        return pkg.replace("-", " ").replace("_", " ").title()
    if len(pkg) <= 4:
        return pkg.upper()
    return pkg[:1].upper() + pkg[1:]


def _preview_question_text(t: QuestionTemplate) -> str:
    """Short preview of template wording (placeholders kept literal)."""
    q = (t.question or "").strip()
    if len(q) > 220:
        return q[:217] + "…"
    return q


def _preview_answer_options(t: QuestionTemplate) -> str:
    ao = (t.answer_options or "").strip()
    if len(ao) > 120:
        return ao[:117] + "…"
    return ao


def explain_template(t: QuestionTemplate) -> list[str]:
    """Human-readable bullets for the UI when a template is selected."""

    lines: list[str] = []
    if t.question_family == "event":
        lines.append(
            "One output row per scheduled game in your date window for each enabled "
            "event-style template. Teams, dates, and answer options are taken from "
            "your schedule; the model only polishes the question wording."
        )
        if t.answer_type == "yes_no":
            lines.append('Answers are fixed to "Yes" / "No".')
        else:
            lines.append(
                "Answer options are built from the matchup (e.g. home vs away), not invented by the model."
            )
        if t.line is not None:
            lines.append(
                f"This template uses a numeric line ({t.line}) in the prompt; "
                "thresholds are still enforced in code from config."
            )
    else:
        lines.append(
            "One output row per game that has enough player stats. Answer choices "
            "are only players returned from your stats file for that game’s teams — "
            "the model does not invent names."
        )
        if t.stat_column:
            lines.append(
                f"Players are ranked by the `{t.stat_column}` column in stats; "
                f"top {t.top_n_per_team or '?'} per team are offered as options."
            )

    if t._comment:
        lines.append(f"Author note: {t._comment}")

    return lines


def template_to_ui_dict(t: QuestionTemplate, *, enabled: bool) -> dict[str, Any]:
    """Serialize a template for the Flask UI (preview + explainer)."""

    return {
        "id": t.id,
        "subcategory": t.subcategory,
        "enabled": enabled,
        "question_family": t.question_family,
        "answer_type": t.answer_type,
        "priority": t.priority,
        "preview_question": _preview_question_text(t),
        "preview_answer_options": _preview_answer_options(t),
        "line": t.line,
        "stat_column": t.stat_column,
        "top_n_per_team": t.top_n_per_team,
        "requires_entities": t.requires_entities,
        "comment": t._comment or "",
        "explainer": explain_template(t),
    }
