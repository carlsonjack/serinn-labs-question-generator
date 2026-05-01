"""Output row assembly (EPIC 5, Task 5.3).

Combines LLM-generated question text with deterministic fields pulled from
templates, config, and the date rule engine to produce upload-ready output rows.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

from core.date_rules import compute_question_dates
from core.input_slots import get_inputs_category_key
from core.parsers.contracts import NormalizedEvent
from core.template_config.schema import QuestionTemplate

from .prompt_builder import GeneratedQuestion, PromptItem

logger = logging.getLogger(__name__)

OUTPUT_COLUMNS: list[str] = [
    "category_id",
    "subcategory",
    "event",
    "question",
    "answer_type",
    "answer_options",
    "start_date",
    "expiration_date",
    "resolution_date",
    "priority_flag",
]


@dataclass
class OutputRow:
    """One upload-ready row conforming to the client CSV schema."""

    category_id: str
    subcategory: str
    event: str
    question: str
    answer_type: str
    answer_options: str
    start_date: str
    expiration_date: str
    resolution_date: str
    priority_flag: str

    def to_dict(self) -> dict[str, str]:
        """Return an ordered dict matching :data:`OUTPUT_COLUMNS`."""
        d = asdict(self)
        return {col: d[col] for col in OUTPUT_COLUMNS}


def build_event_string(event: NormalizedEvent) -> str:
    """Construct the human-readable event string (e.g. ``'Mets vs Yankees'``).

    When ``event_display`` is set, use it (calendar-style labels); otherwise use
    the head-to-head ``away vs home`` pattern.
    """

    if event.event_display and str(event.event_display).strip():
        return str(event.event_display).strip()
    return f"{event.away_team} vs {event.home_team}"


class RowAssembler:
    """Assembles complete output rows from generated questions.

    Parameters
    ----------
    settings:
        Global settings dict (from ``load_settings``).  Used for
        ``category_id`` and passed through to the date rule engine.
    """

    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        self.category_id: str = str(settings.get("category_id", ""))

    def _resolved_category_id(self) -> str:
        pkg = get_inputs_category_key(self.settings).strip().lower()
        cats = self.settings.get("category_ids")
        if isinstance(cats, dict):
            hit = cats.get(pkg)
            if hit is not None and str(hit).strip():
                return str(hit).strip()
        return str(self.settings.get("category_id", ""))

    def assemble(
        self,
        generated: GeneratedQuestion,
        item: PromptItem,
    ) -> OutputRow:
        """Build a single output row from an LLM result and its source item."""
        template = item.template
        event = item.event

        dates = compute_question_dates(
            event.event_datetime,
            category_key=template.subcategory.lower(),
            settings=self.settings,
        )

        return OutputRow(
            category_id=self._resolved_category_id(),
            subcategory=template.subcategory,
            event=build_event_string(event),
            question=generated.question,
            answer_type=template.answer_type,
            answer_options=generated.answer_options,
            start_date=dates.start_date,
            expiration_date=dates.expiration_date,
            resolution_date=dates.resolution_date,
            priority_flag=template.priority,
        )

    def assemble_batch(
        self,
        generated_questions: list[GeneratedQuestion],
        items: list[PromptItem],
    ) -> list[OutputRow]:
        """Assemble rows for a batch of generated questions.

        ``generated_questions`` and ``items`` are matched by position when
        their ``template_id`` / ``event_id`` pairs align.  When the lists
        arrive pre-matched (same order), positional pairing is used directly.
        When the LLM reorders results, the assembler falls back to key-based
        matching on ``(template_id, event_id)``.
        """
        if not generated_questions:
            return []

        if self._positional_match(generated_questions, items):
            return self._assemble_positional(generated_questions, items)

        return self._assemble_by_key(generated_questions, items)

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _positional_match(
        questions: list[GeneratedQuestion],
        items: list[PromptItem],
    ) -> bool:
        if len(questions) != len(items):
            return False
        return all(
            q.template_id == it.template.id and q.event_id == it.event.event_id
            for q, it in zip(questions, items)
        )

    def _assemble_positional(
        self,
        questions: list[GeneratedQuestion],
        items: list[PromptItem],
    ) -> list[OutputRow]:
        return [self.assemble(q, it) for q, it in zip(questions, items)]

    def _assemble_by_key(
        self,
        questions: list[GeneratedQuestion],
        items: list[PromptItem],
    ) -> list[OutputRow]:
        item_map: dict[tuple[str, str], PromptItem] = {
            (it.template.id, it.event.event_id): it for it in items
        }
        rows: list[OutputRow] = []
        for q in questions:
            key = (q.template_id, q.event_id)
            item = item_map.get(key)
            if item is None:
                logger.warning(
                    "No matching PromptItem for generated question "
                    "(template_id=%r, event_id=%r) — skipping row",
                    q.template_id,
                    q.event_id,
                )
                continue
            rows.append(self.assemble(q, item))
        return rows
