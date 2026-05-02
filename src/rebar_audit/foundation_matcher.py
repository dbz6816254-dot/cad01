"""기초 일람표 vs 샵도면 정합성 매처.

알고리즘:
1. 두께 표기(T800 등) 제외, 일람표에 정의된 부재만 대상
2. 각 콜아웃을 가장 가까운 부재 부호(같은 이름)에 배정
3. 부재별로 모인 콜아웃의 (직경, 간격) 다수결로 실측 사양 결정
4. 일람표 사양(X-X / Y-Y)과 비교 → 일치/불일치/누락 판정
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Literal

from rebar_audit.schedule_pdf import FoundationSpec
from rebar_audit.shop import Callout, MemberMark, ShopDrawing

Status = Literal[
    "ok",
    "diameter_mismatch",
    "spacing_mismatch",
    "both_mismatch",
    "missing_callouts",
    "missing_in_schedule",
]

# 두께 표기는 부재 부호에서 제외
THICKNESS_PREFIX = ("T",)


@dataclass(frozen=True)
class MemberMatch:
    """부재 부호별 매칭 결과."""

    name: str
    instance_count: int
    schedule: FoundationSpec | None  # 일람표 사양 (없으면 None)
    observed_dia_spacing: (
        tuple[tuple[int, int | None], int] | None
    )  # ((dia, spacing), count) — 다수결 결과
    callout_count: int
    status: Status
    notes: tuple[str, ...]


def _is_real_member(name: str) -> bool:
    """T800, T1000 같은 두께 표기는 부재가 아님."""
    if not name:
        return False
    if name.startswith(THICKNESS_PREFIX) and name[1:].isdigit():
        return False
    return True


def assign_callouts_to_members(
    sd: ShopDrawing,
    member_names: set[str],
    max_distance_mm: float = 1500.0,
) -> tuple[dict[str, list[Callout]], list[Callout]]:
    """각 콜아웃을 가장 가까운 부재 인스턴스에 배정 (거리 임계값 내에서만).

    - max_distance_mm 초과 시 미할당으로 분류 (false positive 방지)
    - 반환: (부재명→콜아웃 리스트, 미할당 콜아웃 리스트)
    """
    real_members = [m for m in sd.members if m.name in member_names]
    by_member: dict[str, list[Callout]] = defaultdict(list)
    unassigned: list[Callout] = []
    if not real_members:
        return by_member, list(sd.callouts)

    for c in sd.callouts:
        best_name = None
        best_dist = math.inf
        for m in real_members:
            d = math.hypot(c.x - m.x, c.y - m.y)
            if d < best_dist:
                best_dist = d
                best_name = m.name
        if best_name is not None and best_dist <= max_distance_mm:
            by_member[best_name].append(c)
        else:
            unassigned.append(c)
    return by_member, unassigned


def compare_foundation(
    schedule: list[FoundationSpec],
    shops: list[ShopDrawing],
    max_distance_mm: float = 1500.0,
) -> tuple[list[MemberMatch], int]:
    """기초 일람표와 (1개 이상의) 샵도면을 비교.

    여러 샵도면(상/하부근 등)에서 같은 부재의 콜아웃을 모두 모아 다수결.
    반환: (부재 매치 리스트, 미할당 콜아웃 총 개수)
    """
    schedule_map = {s.name: s for s in schedule}
    schedule_names = set(schedule_map)

    # 모든 샵도면에서 발견된 실 부재 이름 (두께 제외)
    shop_member_names: set[str] = set()
    for sd in shops:
        for m in sd.members:
            if _is_real_member(m.name):
                shop_member_names.add(m.name)

    # 콜아웃을 부재별로 모음 (전체 도면 통합)
    combined_assignments: dict[str, list[Callout]] = defaultdict(list)
    total_unassigned = 0
    for sd in shops:
        assignments, unassigned = assign_callouts_to_members(
            sd, shop_member_names | schedule_names, max_distance_mm=max_distance_mm
        )
        for name, cs in assignments.items():
            combined_assignments[name].extend(cs)
        total_unassigned += len(unassigned)

    # 부재별 인스턴스 수 (모든 샵도면 합)
    instance_counts: Counter[str] = Counter()
    for sd in shops:
        for m in sd.members:
            if _is_real_member(m.name):
                instance_counts[m.name] += 1

    matches: list[MemberMatch] = []
    seen: set[str] = set()

    for name in sorted(schedule_names | shop_member_names):
        if not _is_real_member(name):
            continue
        seen.add(name)
        spec = schedule_map.get(name)
        callouts = combined_assignments.get(name, [])
        instances = instance_counts.get(name, 0)

        # 다수결로 실측 사양 결정
        spec_counter: Counter[tuple[int, int | None]] = Counter()
        for c in callouts:
            spec_counter[(c.diameter, c.spacing)] += c.count
        observed: tuple[tuple[int, int | None], int] | None
        observed = spec_counter.most_common(1)[0] if spec_counter else None

        notes: list[str] = []
        status: Status

        if spec is None:
            status = "missing_in_schedule"
            notes.append(f"일람표에 정의 없음 (샵도면에는 {instances}개 인스턴스)")
        elif observed is None:
            status = "missing_callouts"
            notes.append(f"샵도면에서 주변 콜아웃을 찾지 못함 (인스턴스 {instances}개)")
        else:
            (obs_dia, obs_sp), _ = observed
            sched_dia = spec.dia_x  # X-X / Y-Y 동일 가정 (이 일람표에서는 같음)
            sched_sp = spec.spacing_x
            dia_ok = obs_dia == sched_dia
            sp_ok = obs_sp == sched_sp

            if dia_ok and sp_ok:
                status = "ok"
            elif not dia_ok and not sp_ok:
                status = "both_mismatch"
                notes.append(f"직경 D{obs_dia}≠D{sched_dia}, 간격 @{obs_sp}≠@{sched_sp}")
            elif not dia_ok:
                status = "diameter_mismatch"
                notes.append(f"직경 D{obs_dia}≠D{sched_dia}")
            else:
                status = "spacing_mismatch"
                notes.append(f"간격 @{obs_sp}≠@{sched_sp}")

            # X-X / Y-Y 비대칭이면 추가 경고
            if spec.dia_x != spec.dia_y or spec.spacing_x != spec.spacing_y:
                notes.append(
                    f"일람표 X-X(D{spec.dia_x}@{spec.spacing_x}) / "
                    f"Y-Y(D{spec.dia_y}@{spec.spacing_y}) — 방향별 사양 다름"
                )

        matches.append(
            MemberMatch(
                name=name,
                instance_count=instances,
                schedule=spec,
                observed_dia_spacing=observed,
                callout_count=sum(c.count for c in callouts),
                status=status,
                notes=tuple(notes),
            )
        )

    return matches, total_unassigned
