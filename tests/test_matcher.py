"""매처 테스트: Stage 1 직경별 / Stage 2 부호별."""

from __future__ import annotations

from rebar_audit.fixtures import mismatched_invoice_items, reference_items
from rebar_audit.matcher import (
    aggregate_by_diameter,
    aggregate_by_mark,
    compare_by_diameter,
    compare_by_mark,
)
from rebar_audit.models import RebarSet


def _set(items, origin="schedule"):
    return RebarSet(source_path="test", source_kind="excel", origin=origin, items=items)


def test_aggregate_by_diameter_groups_correctly():
    rs = _set(reference_items())
    agg = aggregate_by_diameter(rs)
    assert agg[10].count == 140  # S1(60) + S2(80)
    assert agg[13].count == 40
    assert agg[16].count == 20
    assert agg[22].count == 12


def test_compare_by_diameter_perfect_match():
    a = _set(reference_items())
    b = _set(reference_items(), origin="invoice")
    diffs = compare_by_diameter(a, b)
    assert all(d.status == "ok" for d in diffs)
    assert all(abs(d.weight_delta_pct) < 0.01 for d in diffs)


def test_compare_by_diameter_detects_mismatch():
    a = _set(reference_items())
    b = _set(mismatched_invoice_items(), origin="invoice")
    diffs = {d.diameter: d for d in compare_by_diameter(a, b)}
    # D13: 송장에 절반(20)만 → ~50% 미달 → error
    assert diffs[13].status == "error"
    assert diffs[13].weight_delta_pct < -40
    # D22: 12 → 7 → ~41% 미달 → error
    assert diffs[22].status == "error"
    # D10, D16: 일치
    assert diffs[10].status == "ok"
    assert diffs[16].status == "ok"


def test_compare_by_diameter_within_tolerance():
    """허용오차 ±2% 내의 작은 차이는 ok."""
    from rebar_audit.models import BarItem

    a = _set([BarItem(diameter=16, length_mm=1000, count=1000)])
    # 길이만 0.5% 줄임 → 무게 차이 ~0.5% < 2%
    b = _set(
        [BarItem(diameter=16, length_mm=995, count=1000)],
        origin="invoice",
    )
    diffs = {d.diameter: d for d in compare_by_diameter(a, b, weight_tol_pct=2.0)}
    assert diffs[16].status == "ok"
    assert abs(diffs[16].weight_delta_pct) < 2.0


def test_compare_by_mark_skips_when_one_side_missing():
    a = _set(reference_items())  # 부호 있음
    b_items = [item.model_copy(update={"mark": None}) for item in reference_items()]
    b = _set(b_items, origin="invoice")  # 부호 없음
    assert compare_by_mark(a, b) == []


def test_compare_by_mark_detects_mismatch():
    a = _set(reference_items())
    b = _set(mismatched_invoice_items(), origin="invoice")
    diffs = {d.mark: d for d in compare_by_mark(a, b)}
    assert diffs["B1"].status == "ok"
    assert diffs["B2"].status == "error"
    assert "개수" in diffs["B2"].notes[0]
    assert diffs["M1"].status == "error"


def test_aggregate_by_mark_combines_split_rows():
    items = [
        # 동일 부호 두 행: 분할된 가공도 가정
        type(reference_items()[0])(mark="X1", diameter=16, length_mm=2000, count=10),
        type(reference_items()[0])(mark="X1", diameter=16, length_mm=2000, count=5),
    ]
    rs = _set(items)
    agg = aggregate_by_mark(rs)
    assert agg["X1"].count == 15
