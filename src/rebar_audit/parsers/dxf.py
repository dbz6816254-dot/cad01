"""DXF 시공상세도 파서 (ezdxf).

지원 추출 방식:
1. ATTRIB 기반: INSERT 엔티티의 ATTRIB 태그로 MARK/DIA/LEN/CNT 추출 (권장)
2. 텍스트 콜아웃: TEXT/MTEXT 패턴 '수량-D직경 L=길이'
"""

from __future__ import annotations

import re
from pathlib import Path

import ezdxf
from ezdxf.document import Drawing

from rebar_audit.models import BarItem, Origin, RebarSet

# ATTRIB 태그 동의어 (대문자 비교)
ATTRIB_ALIASES: dict[str, tuple[str, ...]] = {
    "mark": ("MARK", "BAR", "부호", "기호"),
    "diameter": ("DIA", "DIAMETER", "직경", "D"),
    "length": ("LEN", "LENGTH", "L", "길이"),
    "count": ("CNT", "QTY", "COUNT", "EA", "수량"),
    "bend_type": ("SHAPE", "BEND", "형상"),
}

# 콜아웃 패턴: '12-D16 L=2400' / '12-HD16 L=2400' / '12개 D16 L2400'
_CALLOUT_RE = re.compile(
    r"(?P<count>\d+)\s*[-개ea]?\s*(?:H?D|φ)?(?P<dia>\d{1,2})\s*(?:L\s*=?\s*)?(?P<length>\d{3,5})",
    re.IGNORECASE,
)


def _extract_from_attribs(doc: Drawing) -> list[BarItem]:
    items: list[BarItem] = []
    msp = doc.modelspace()
    for insert in msp.query("INSERT"):
        attribs: dict[str, str] = {a.dxf.tag.upper(): str(a.dxf.text) for a in insert.attribs}
        if not attribs:
            continue
        values: dict[str, str | None] = {}
        for field, aliases in ATTRIB_ALIASES.items():
            for alias in aliases:
                key = alias.upper()
                if key in attribs and attribs[key]:
                    values[field] = attribs[key]
                    break
        try:
            diameter = _digit_only(values.get("diameter"))
            length = _digit_only(values.get("length"))
            count = _digit_only(values.get("count"))
            if diameter is None or length is None or count is None:
                continue
            items.append(
                BarItem(
                    mark=values.get("mark"),
                    diameter=diameter,
                    length_mm=length,
                    count=count,
                    bend_type=values.get("bend_type"),
                )
            )
        except (ValueError, TypeError):
            continue
    return items


def _extract_from_text(doc: Drawing) -> list[BarItem]:
    items: list[BarItem] = []
    msp = doc.modelspace()
    for entity in msp.query("TEXT MTEXT"):
        text = entity.plain_text() if hasattr(entity, "plain_text") else str(entity.dxf.text)
        for m in _CALLOUT_RE.finditer(text):
            try:
                items.append(
                    BarItem(
                        diameter=int(m.group("dia")),
                        length_mm=int(m.group("length")),
                        count=int(m.group("count")),
                    )
                )
            except (ValueError, TypeError):
                continue
    return items


def _digit_only(s: str | None) -> int | None:
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


def parse_dxf(path: str | Path, origin: Origin = "drawing") -> RebarSet:
    """DXF 파일에서 철근 항목 추출."""
    p = Path(path)
    doc = ezdxf.readfile(str(p))

    items = _extract_from_attribs(doc)
    if not items:
        items = _extract_from_text(doc)

    return RebarSet(source_path=str(p), source_kind="dxf", origin=origin, items=items)
