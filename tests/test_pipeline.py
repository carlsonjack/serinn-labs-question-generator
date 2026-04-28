"""Pipeline helpers (Epic 8)."""

from __future__ import annotations

from core.pipeline import filter_templates_for_subcategory, is_template_enabled
from core.template_config.schema import QuestionTemplate


def _tpl(tid: str, sub: str = "MLB") -> QuestionTemplate:
    return QuestionTemplate(
        id=tid,
        subcategory=sub,
        question_family="event",
        question="Q",
        answer_type="yes_no",
        answer_options="Yes||No",
        priority="false",
        requires_entities=False,
    )


def test_filter_templates_respects_subcategory_and_enabled():
    templates = {
        "a": _tpl("mlb_a", "MLB"),
        "b": _tpl("mlb_b", "MLB"),
        "c": _tpl("mkt", "Markets"),
    }
    settings = {"templates_enabled": {"mlb_a": True, "mlb_b": False}}
    out = filter_templates_for_subcategory(templates, "MLB", settings)
    assert [t.id for t in out] == ["mlb_a"]


def test_filter_templates_normalizes_subcategory_text():
    templates = {
        "a": _tpl("mlb_a", "MLB"),
        "b": _tpl("ent", "Entertainment"),
    }
    out = filter_templates_for_subcategory(templates, "mlb", {"templates_enabled": {}})
    assert [t.id for t in out] == ["mlb_a"]


def test_is_template_enabled_defaults():
    assert is_template_enabled("x", {}) is True
    assert is_template_enabled("x", {"templates_enabled": None}) is True


def test_format_generation_failure_quota_message():
    from core.generation.batch_executor import BatchResult, FailedBatch
    from core.pipeline import _format_generation_failure_message

    br = BatchResult(
        failed_batches=[
            FailedBatch(
                batch_index=0,
                item_count=5,
                error="Error code: 429 - {'error': {'code': 'insufficient_quota'}}",
            )
        ]
    )
    msg = _format_generation_failure_message(br)
    assert "billing" in msg.lower() or "quota" in msg.lower()
    assert "OpenAI" in msg


def test_max_generated_questions_helper():
    from core.pipeline import _max_generated_questions

    assert _max_generated_questions({}) is None
    assert _max_generated_questions({"max_generated_questions": None}) is None
    assert _max_generated_questions({"max_generated_questions": ""}) is None
    assert _max_generated_questions({"max_generated_questions": 0}) is None
    assert _max_generated_questions({"max_generated_questions": 5}) == 5


def test_successful_prompt_items_skips_failed_batch():
    from core.generation import PromptItem
    from core.generation.batch_executor import BatchResult, FailedBatch
    from core.parsers.contracts import NormalizedEvent
    from core.pipeline import _successful_prompt_items

    ev = NormalizedEvent(
        event_id="1",
        home_team="A",
        away_team="B",
        event_datetime="2026-05-15T21:40:00",
        subcategory="MLB",
    )
    t = _tpl("t1")
    items = [PromptItem(template=t, event=ev, players=[])] * 5
    br = BatchResult(failed_batches=[FailedBatch(batch_index=0, item_count=5, error="x")])
    assert _successful_prompt_items(items, br, batch_size=5) == []
