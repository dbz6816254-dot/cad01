"""파일 확장자 기반 자동 디스패치."""

from __future__ import annotations

from pathlib import Path

from rebar_audit.models import Origin, RebarSet


def parse(path: str | Path, origin: Origin = "schedule") -> RebarSet:
    """확장자에 따라 적절한 파서로 라우팅.

    - .xlsx/.xlsm/.csv → excel
    - .pdf            → pdf
    - .dxf            → dxf
    - .dwg            → dwg (DXF 자동 변환 시도)
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in (".xlsx", ".xlsm", ".csv"):
        from rebar_audit.parsers.excel import parse_excel

        return parse_excel(p, origin=origin)
    if suffix == ".pdf":
        from rebar_audit.parsers.pdf import parse_pdf

        return parse_pdf(p, origin=origin)
    if suffix == ".dxf":
        from rebar_audit.parsers.dxf import parse_dxf

        return parse_dxf(p, origin=origin)
    if suffix == ".dwg":
        from rebar_audit.parsers.dwg import parse_dwg

        return parse_dwg(p, origin=origin)
    raise ValueError(f"지원하지 않는 확장자: {suffix}")
