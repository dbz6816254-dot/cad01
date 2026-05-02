"""파서 통합 테스트 (Excel/PDF/DXF)."""

from __future__ import annotations

from rebar_audit.parsers.dxf import parse_dxf
from rebar_audit.parsers.excel import _detect_columns, parse_excel
from rebar_audit.parsers.pdf import parse_pdf


def test_detect_columns_korean_headers():
    mapping = _detect_columns(["번호", "부호", "직경", "단위길이", "개수", "형상"])
    assert mapping["부호"] == "mark"
    assert mapping["직경"] == "diameter"
    assert mapping["단위길이"] == "length"
    assert mapping["개수"] == "count"
    assert mapping["형상"] == "bend_type"


def test_detect_columns_english_invoice_headers():
    mapping = _detect_columns(["NAME", "SPEC", "LENGTH", "QTY"])
    assert mapping["SPEC"] == "diameter"
    assert mapping["LENGTH"] == "length"
    assert mapping["QTY"] == "count"


def test_excel_parser_roundtrip(sample_paths):
    rs = parse_excel(sample_paths["bbs_xlsx"], origin="schedule")
    assert len(rs.items) == 5
    assert rs.origin == "schedule"
    diameters = sorted({i.diameter for i in rs.items})
    assert diameters == [10, 13, 16, 22]


def test_excel_parser_invoice_no_marks(sample_paths):
    rs = parse_excel(sample_paths["invoice_match_xlsx"], origin="invoice")
    assert len(rs.items) == 5
    # 송장 형식: 부호 컬럼 없음
    assert all(item.mark is None for item in rs.items)


def test_pdf_parser_extracts_invoice(sample_paths):
    rs = parse_pdf(sample_paths["invoice_match_pdf"], origin="invoice")
    # PDF 표 추출이 5행을 잡는지
    assert len(rs.items) == 5
    diameters = sorted({i.diameter for i in rs.items})
    assert diameters == [10, 13, 16, 22]


def test_dxf_parser_attribs(sample_paths):
    rs = parse_dxf(sample_paths["drawing_dxf"], origin="drawing")
    assert len(rs.items) == 5
    marks = sorted(i.mark for i in rs.items if i.mark)
    assert marks == ["B1", "B2", "M1", "S1", "S2"]
