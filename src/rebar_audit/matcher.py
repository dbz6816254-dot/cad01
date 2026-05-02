"""정합성 비교: Stage 1(직경별 총량) + Stage 2(부호별 1:1)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from rebar_audit.models import BarItem, RebarSet, unit_weight

Status = Literal["ok", "warning", "error", "missing_a", "missing_b"]


@dataclass(frozen=True)
class DiameterSummary:
    diameter: int
    count: int
    total_length_m: float
    total_weight_kg: float


@dataclass(frozen=True)
class DiameterDiff:
    diameter: int
    a_count: int
    b_count: int
    a_length_m: float
    b_length_m: float
    a_weight_kg: float
    b_weight_kg: float
    weight_delta_kg: float
    weight_delta_pct: float
    status: Status


@dataclass(frozen=True)
class MarkSummary:
    mark: str
    diameter: int
    length_mm: int
    count: int
    bend_type: str | None


@dataclass(frozen=True)
class MarkDiff:
    mark: str
    a: MarkSummary | None
    b: MarkSummary | None
    status: Status
    notes: tuple[str, ...]


def aggregate_by_diameter(rs: RebarSet) -> dict[int, DiameterSummary]:
    bucket: dict[int, list[BarItem]] = defaultdict(list)
    for item in rs.items:
        bucket[item.diameter].append(item)
    out: dict[int, DiameterSummary] = {}
    for d, items in bucket.items():
        count = sum(i.count for i in items)
        length_m = sum(i.total_length_m for i in items)
        weight_kg = unit_weight(d) * length_m
        out[d] = DiameterSummary(
            diameter=d,
            count=count,
            total_length_m=round(length_m, 3),
            total_weight_kg=round(weight_kg, 3),
        )
    return out


def aggregate_by_mark(rs: RebarSet) -> dict[str, MarkSummary]:
    """부호 컬럼이 있는 항목만 부호별로 집계.

    동일 부호가 여러 행으로 나뉘어 있으면 직경/길이가 같다고 가정하고 count 합산.
    직경/길이가 다르면 첫 번째 항목 기준, 이후는 무시(경고는 호출부에서 발견).
    """
    out: dict[str, MarkSummary] = {}
    for item in rs.items:
        if not item.mark:
            continue
        existing = out.get(item.mark)
        if existing is None:
            out[item.mark] = MarkSummary(
                mark=item.mark,
                diameter=item.diameter,
                length_mm=item.length_mm,
                count=item.count,
                bend_type=item.bend_type,
            )
        else:
            # 같은 부호의 추가 행: 가공도/송장이 분할된 경우. 직경·길이가 같으면 합산.
            if existing.diameter == item.diameter and existing.length_mm == item.length_mm:
                out[item.mark] = MarkSummary(
                    mark=existing.mark,
                    diameter=existing.diameter,
                    length_mm=existing.length_mm,
                    count=existing.count + item.count,
                    bend_type=existing.bend_type or item.bend_type,
                )
    return out


def compare_by_diameter(
    a: RebarSet,
    b: RebarSet,
    weight_tol_pct: float = 2.0,
) -> list[DiameterDiff]:
    """직경별 총중량을 비교. 허용오차(±%)를 벗어나면 warning/error."""
    agg_a = aggregate_by_diameter(a)
    agg_b = aggregate_by_diameter(b)
    diameters = sorted(set(agg_a) | set(agg_b))
    diffs: list[DiameterDiff] = []
    for d in diameters:
        sa = agg_a.get(d)
        sb = agg_b.get(d)
        a_count = sa.count if sa else 0
        b_count = sb.count if sb else 0
        a_len = sa.total_length_m if sa else 0.0
        b_len = sb.total_length_m if sb else 0.0
        a_w = sa.total_weight_kg if sa else 0.0
        b_w = sb.total_weight_kg if sb else 0.0
        delta = round(b_w - a_w, 3)
        denom = a_w if a_w else (b_w if b_w else 1.0)
        pct = round(100.0 * delta / denom, 2) if denom else 0.0

        status: Status
        if sa is None:
            status = "missing_a"
        elif sb is None:
            status = "missing_b"
        elif abs(pct) <= weight_tol_pct:
            status = "ok"
        elif abs(pct) <= weight_tol_pct * 2:
            status = "warning"
        else:
            status = "error"

        diffs.append(
            DiameterDiff(
                diameter=d,
                a_count=a_count,
                b_count=b_count,
                a_length_m=round(a_len, 3),
                b_length_m=round(b_len, 3),
                a_weight_kg=round(a_w, 3),
                b_weight_kg=round(b_w, 3),
                weight_delta_kg=delta,
                weight_delta_pct=pct,
                status=status,
            )
        )
    return diffs


def compare_by_mark(a: RebarSet, b: RebarSet) -> list[MarkDiff]:
    """부호별 1:1 비교. 직경/길이/개수 일치 여부.

    한쪽에 부호가 전혀 없으면 빈 리스트 반환 (Stage 2 스킵).
    """
    agg_a = aggregate_by_mark(a)
    agg_b = aggregate_by_mark(b)
    if not agg_a or not agg_b:
        return []
    marks = sorted(set(agg_a) | set(agg_b))
    diffs: list[MarkDiff] = []
    for mark in marks:
        ma = agg_a.get(mark)
        mb = agg_b.get(mark)
        notes: list[str] = []
        if ma is None:
            diffs.append(MarkDiff(mark=mark, a=None, b=mb, status="missing_a", notes=()))
            continue
        if mb is None:
            diffs.append(MarkDiff(mark=mark, a=ma, b=None, status="missing_b", notes=()))
            continue
        if ma.diameter != mb.diameter:
            notes.append(f"직경 불일치: {ma.diameter} vs {mb.diameter}")
        if ma.length_mm != mb.length_mm:
            notes.append(f"길이 불일치: {ma.length_mm} vs {mb.length_mm}")
        if ma.count != mb.count:
            notes.append(f"개수 불일치: {ma.count} vs {mb.count}")
        status: Status = "ok" if not notes else "error"
        diffs.append(MarkDiff(mark=mark, a=ma, b=mb, status=status, notes=tuple(notes)))
    return diffs
