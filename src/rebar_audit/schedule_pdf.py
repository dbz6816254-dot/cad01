"""원본도면 일람표 PDF에서 부재별 사양 추출.

기초 일람표 행 예시:
    F1   A   800   3000 2200   D19 @250   D19 @250
    F3   A   1000  3500 2500   D19 @200   D19 @200
    ...
컬럼: NAME / TYPE / 두께 / Lx / Ly / X-X 방향 / Y-Y 방향 / REMARK
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

# 한 행에서 부재 사양 추출
# F4A   A   1100   3500 3500   D19 @150   D19 @150
ROW_RE = re.compile(
    r"(?P<name>[A-Z]{1,4}\d{1,3}[A-Z]?)\s+"
    r"(?P<type>[A-Z])\s+"
    r"(?P<thk>\d{3,4})\s+"
    r"(?P<lx>\d{3,5})\s+"
    r"(?P<ly>\d{3,5}|-)\s+"
    r"D(?P<dia_x>\d{1,2})\s*@\s*(?P<sp_x>\d{2,4})\s+"
    r"D(?P<dia_y>\d{1,2})\s*@\s*(?P<sp_y>\d{2,4})"
)


@dataclass(frozen=True)
class FoundationSpec:
    """기초 일람표 한 부재의 설계 사양."""

    name: str
    type_: str
    thickness_mm: int
    lx_mm: int
    ly_mm: int | None
    dia_x: int
    spacing_x: int
    dia_y: int
    spacing_y: int


def parse_foundation_schedule_pdf(path: str | Path) -> list[FoundationSpec]:
    """기초 일람표 PDF에서 모든 F-/WF- 부재 사양 추출.

    표 구조 인식이 실패할 경우를 대비해 텍스트 라인을 정규식으로 직접 매칭.
    """
    p = Path(path)
    specs: list[FoundationSpec] = []
    seen: set[str] = set()

    with pdfplumber.open(p) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                m = ROW_RE.search(line)
                if not m:
                    continue
                if m.group("name") in seen:
                    continue
                seen.add(m.group("name"))
                ly_str = m.group("ly")
                specs.append(
                    FoundationSpec(
                        name=m.group("name"),
                        type_=m.group("type"),
                        thickness_mm=int(m.group("thk")),
                        lx_mm=int(m.group("lx")),
                        ly_mm=None if ly_str == "-" else int(ly_str),
                        dia_x=int(m.group("dia_x")),
                        spacing_x=int(m.group("sp_x")),
                        dia_y=int(m.group("dia_y")),
                        spacing_y=int(m.group("sp_y")),
                    )
                )
    return specs
