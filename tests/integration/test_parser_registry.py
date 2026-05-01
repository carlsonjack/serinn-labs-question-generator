"""Integration-lite: normalizer registry contracts."""

from __future__ import annotations

import pytest

from core.parsers.registry import get_category_normalizer, list_registered_categories


@pytest.mark.integration
def test_registered_verticals_include_mlb_and_f1() -> None:
    cats = list_registered_categories()
    assert "mlb" in cats
    assert "f1" in cats


@pytest.mark.integration
def test_get_category_normalizer_lowercase_keys() -> None:
    assert get_category_normalizer("mlb").__name__ == "MlbCategoryNormalizer"
    assert get_category_normalizer("f1").__name__ == "F1CategoryNormalizer"
