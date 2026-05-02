"""샵도면(시공상세도) 콜아웃 파서 + 부재 위치 매핑.

도면 콜아웃 패턴 예시 (한국 시공도 표준):
    [1] 55-SHD13@200(8000)        부호번호 1, 55개, S형 D13, @200간격, L=8000
    [20] 28-UHD19@250(10000)      부호번호 20, 28개, U형 D19, @250간격, L=10000
    [62] 25-UHD19@250-F(310+3400) 부호번호 62, 25개, U형 D19, @250, F형상, 310+3400
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import ezdxf
from ezdxf.document import Drawing

# 샵도면 콜아웃 정규식
CALLOUT_RE = re.compile(
    r"\[(?P<id>\d+)\]\s*"
    r"(?P<count>\d+)-"
    r"(?P<shape>[A-Z]+)D(?P<dia>\d{1,2})"
    r"(?:@(?P<spacing>\d{1,4}))?"
    r"(?:-(?P<bend>[A-Z]+))?"
    r"\((?P<length>[^)]+)\)"
)

# 부재 부호 패턴: F1, F4A, WF1, RPW1, BT1 등
MEMBER_MARK_RE = re.compile(r"^[A-Z]{1,4}\d{1,3}[A-Z]?$")

# 두께 표기: T800, T1000, T1100, T1200, T1300
THICKNESS_RE = re.compile(r"^T(\d{3,4})$")
MAT_THK_RE = re.compile(r"MAT\s*THK\.?\s*(\d{3,4})", re.IGNORECASE)


@dataclass(frozen=True)
class Callout:
    """샵도면 한 콜아웃."""

    callout_id: int  # [1], [2], [62] ... 도면 내 부호번호
    count: int
    shape: str  # SH, UH, S, U 등
    diameter: int
    spacing: int | None  # @ 간격(mm)
    bend: str | None  # F, H 등 굽힘 표기
    length_text: str  # "8000" 또는 "310+3400"
    x: float
    y: float
    raw: str  # 원본 텍스트

    @property
    def length_mm(self) -> int:
        """길이 텍스트를 mm 정수로. '310+3400' → 3710."""
        return sum(int(p) for p in re.findall(r"\d+", self.length_text))

    @property
    def total_length_m(self) -> float:
        return self.count * self.length_mm / 1000


@dataclass(frozen=True)
class MemberMark:
    """샵도면 위에 표시된 부재 부호 (F1, WF1 등) + 좌표."""

    name: str
    x: float
    y: float


@dataclass
class ShopDrawing:
    """샵도면 1장의 추출 결과."""

    path: str
    callouts: list[Callout] = field(default_factory=list)
    members: list[MemberMark] = field(default_factory=list)
    thicknesses: list[tuple[float, float, int]] = field(default_factory=list)

    def callouts_for_member(self, member: MemberMark, radius: float = 5000.0) -> list[Callout]:
        """특정 부재 부호 좌표 반경 내 콜아웃 목록 (가장 가까운 것부터)."""
        in_range = [
            (c, ((c.x - member.x) ** 2 + (c.y - member.y) ** 2) ** 0.5)
            for c in self.callouts
            if ((c.x - member.x) ** 2 + (c.y - member.y) ** 2) ** 0.5 <= radius
        ]
        in_range.sort(key=lambda r: r[1])
        return [c for c, _ in in_range]


def _iter_text_entities(doc: Drawing):
    msp = doc.modelspace()
    for t in msp.query("TEXT"):
        yield t.dxf.text, float(t.dxf.insert.x), float(t.dxf.insert.y)
    for m in msp.query("MTEXT"):
        s = m.plain_text() if hasattr(m, "plain_text") else m.dxf.text
        ip = m.dxf.insert
        yield s, float(ip.x), float(ip.y)


def parse_shop_dxf(path: str | Path) -> ShopDrawing:
    """DXF 샵도면에서 콜아웃·부재부호·두께를 모두 추출."""
    p = Path(path)
    doc = ezdxf.readfile(str(p))
    sd = ShopDrawing(path=str(p))

    for text, x, y in _iter_text_entities(doc):
        s = (text or "").strip()
        if not s:
            continue

        # 콜아웃 추출 (한 텍스트에 여러 콜아웃이 들어있을 수 있음)
        for m in CALLOUT_RE.finditer(s):
            sd.callouts.append(
                Callout(
                    callout_id=int(m.group("id")),
                    count=int(m.group("count")),
                    shape=m.group("shape"),
                    diameter=int(m.group("dia")),
                    spacing=int(m.group("spacing")) if m.group("spacing") else None,
                    bend=m.group("bend"),
                    length_text=m.group("length"),
                    x=x,
                    y=y,
                    raw=s,
                )
            )

        # 부재 부호 (F1, WF1 등)
        if MEMBER_MARK_RE.match(s):
            sd.members.append(MemberMark(name=s, x=x, y=y))

        # 두께 표기
        m_thk = THICKNESS_RE.match(s)
        if m_thk:
            sd.thicknesses.append((x, y, int(m_thk.group(1))))
        m_mat = MAT_THK_RE.search(s)
        if m_mat:
            sd.thicknesses.append((x, y, int(m_mat.group(1))))

    return sd
