"""Template UI metadata."""

from __future__ import annotations

from core.template_config.schema import QuestionTemplate
from core.template_ui import (
    explain_template,
    filter_templates_for_package,
    infer_subcategory_for_package,
    template_to_ui_dict,
)


def _event_tpl() -> QuestionTemplate:
    return QuestionTemplate(
        id="t1",
        subcategory="MLB",
        question_family="event",
        question="Who wins {home_team} vs {away_team}?",
        answer_type="multiple_choice",
        answer_options="{home_team}||{away_team}",
        priority="true",
        requires_entities=False,
    )


def _entity_tpl() -> QuestionTemplate:
    return QuestionTemplate(
        id="t2",
        subcategory="MLB",
        question_family="entity_stat",
        question="Who hits a HR?",
        answer_type="multiple_choice",
        answer_options="{entity_options}",
        priority="false",
        requires_entities=True,
        stat_column="HR",
        top_n_per_team=2,
    )


def test_template_to_ui_dict_has_explainer():
    d = template_to_ui_dict(_event_tpl(), enabled=True)
    assert d["id"] == "t1"
    assert "Who wins" in d["preview_question"]
    assert d["explainer"]
    assert isinstance(d["explainer"], list)


def test_entity_explainer_mentions_stat():
    lines = explain_template(_entity_tpl())
    assert any("HR" in line for line in lines)


def test_filter_templates_for_package_normalizes_case():
    templates = [_event_tpl(), _entity_tpl()]
    out = filter_templates_for_package(templates, "mlb")
    assert [t.id for t in out] == ["t1", "t2"]


def test_infer_subcategory_for_package_prefers_template_value():
    subcategory = infer_subcategory_for_package([_event_tpl()], "mlb")
    assert subcategory == "MLB"
