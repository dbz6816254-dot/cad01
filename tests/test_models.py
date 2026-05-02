"""도메인 모델 테스트."""

from __future__ import annotations

import pytest

from rebar_audit.models import BarItem, RebarSet, unit_weight


def test_unit_weight_known_diameters():
    assert unit_weight(10) == 0.560
    assert unit_weight(13) == 0.995
    assert unit_weight(16) == 1.560
    assert unit_weight(22) == 3.040


def test_unit_weight_unknown_uses_formula():
    assert unit_weight(99) == pytest.approx(0.006165 * 99**2, rel=1e-3)


def test_bar_item_totals():
    item = BarItem(mark="B1", diameter=16, length_mm=2400, count=20)
    assert item.total_length_m == 48.0
    assert item.total_weight_kg == pytest.approx(48.0 * 1.560, rel=1e-3)


def test_bar_item_diameter_validation():
    with pytest.raises(ValueError):
        BarItem(diameter=3, length_mm=100, count=1)


def test_rebar_set_aggregations():
    rs = RebarSet(
        source_path="test",
        source_kind="excel",
        origin="schedule",
        items=[
            BarItem(diameter=10, length_mm=1000, count=10),
            BarItem(diameter=10, length_mm=1500, count=5),
            BarItem(diameter=13, length_mm=2000, count=3),
        ],
    )
    assert rs.total_count() == 18
    assert rs.total_length_m() == pytest.approx(10 + 7.5 + 6.0)
