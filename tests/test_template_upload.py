"""Template upload parsing helpers."""

from __future__ import annotations

import pytest

from core.template_upload import parse_template_csv_blocks, parse_uploaded_template_file


def test_parse_template_csv_blocks_single_template():
    text = (
        "id,subcategory,question_family,question,answer_type,answer_options,priority,requires_entities\n"
        "mlb_game_winner,MLB,event,Who wins?,yes_no,Yes||No,false,false\n"
    )
    rows = parse_template_csv_blocks(text)
    assert rows == [
        {
            "id": "mlb_game_winner",
            "subcategory": "MLB",
            "question_family": "event",
            "question": "Who wins?",
            "answer_type": "yes_no",
            "answer_options": "Yes||No",
            "priority": "false",
            "requires_entities": False,
        }
    ]


def test_parse_template_csv_blocks_multiple_templates():
    text = (
        "id,subcategory,question_family,question,answer_type,answer_options,priority,requires_entities\n"
        "mlb_game_winner,MLB,event,Who wins?,yes_no,Yes||No,false,false\n"
        "id,subcategory,question_family,question,answer_type,answer_options,priority,requires_entities,stat_column,top_n_per_team\n"
        "mlb_home_run,MLB,entity_stat,Who hits a HR?,multiple_choice,{entity_options},false,true,HR,3\n"
    )
    rows = parse_template_csv_blocks(text)
    assert [row["id"] for row in rows] == ["mlb_game_winner", "mlb_home_run"]
    assert rows[1]["requires_entities"] is True
    assert rows[1]["top_n_per_team"] == 3


def test_parse_template_csv_blocks_rejects_odd_rows():
    text = (
        "id,subcategory\n"
        "mlb_game_winner,MLB\n"
        "id,subcategory\n"
    )
    with pytest.raises(ValueError, match="even number of non-empty rows"):
        parse_template_csv_blocks(text)


def test_parse_uploaded_template_file_rejects_bad_bool():
    text = (
        "id,subcategory,question_family,question,answer_type,answer_options,priority,requires_entities\n"
        "mlb_game_winner,MLB,event,Who wins?,yes_no,Yes||No,false,maybe\n"
    )
    with pytest.raises(ValueError, match="boolean"):
        parse_uploaded_template_file("templates.csv", text)
