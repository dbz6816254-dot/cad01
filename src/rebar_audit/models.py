"""도메인 모델: 철근 항목과 집합."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# KS D 3504 기준 이형철근 단위중량 (kg/m). 표준 직경.
UNIT_WEIGHT_KG_PER_M: dict[int, float] = {
    6: 0.222,
    8: 0.395,
    10: 0.560,
    13: 0.995,
    16: 1.560,
    19: 2.250,
    22: 3.040,
    25: 3.980,
    29: 5.040,
    32: 6.230,
    35: 7.510,
    38: 8.950,
    41: 10.500,
    51: 15.900,
}


def unit_weight(diameter_mm: int) -> float:
    """직경(mm)에 대한 단위중량(kg/m). 표 누락 시 0.006165*d^2로 근사."""
    if diameter_mm in UNIT_WEIGHT_KG_PER_M:
        return UNIT_WEIGHT_KG_PER_M[diameter_mm]
    return round(0.006165 * diameter_mm**2, 3)


Origin = Literal["drawing", "schedule", "invoice"]
SourceKind = Literal["dxf", "dwg", "pdf", "excel", "csv"]


class BarItem(BaseModel):
    """단위 철근 항목 (가공도/송장의 한 행, 또는 도면의 한 부호)."""

    mark: str | None = None
    diameter: int = Field(..., ge=6, le=51, description="공칭직경 mm")
    length_mm: int = Field(..., ge=1, description="단위 절단 길이 mm")
    count: int = Field(..., ge=1, description="개수")
    bend_type: str | None = None
    grade: str | None = None

    @field_validator("mark")
    @classmethod
    def _strip_mark(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @property
    def total_length_m(self) -> float:
        return self.length_mm * self.count / 1000

    @property
    def total_weight_kg(self) -> float:
        return unit_weight(self.diameter) * self.total_length_m


class RebarSet(BaseModel):
    """철근 항목 집합. 도면(시공상세도) / 가공도 / 송장 중 한 출처."""

    source_path: str
    source_kind: SourceKind
    origin: Origin
    items: list[BarItem] = Field(default_factory=list)
    project: str | None = None
    issued_at: str | None = None

    def total_count(self) -> int:
        return sum(i.count for i in self.items)

    def total_length_m(self) -> float:
        return sum(i.total_length_m for i in self.items)

    def total_weight_kg(self) -> float:
        return sum(i.total_weight_kg for i in self.items)
