"""더미 데이터 생성기. 샘플 BBS/송장/DXF/PDF 파일 출력."""

from __future__ import annotations

from pathlib import Path

import ezdxf
import pdfplumber  # noqa: F401  # 설치 확인용
from openpyxl import Workbook

from rebar_audit.models import BarItem


def reference_items() -> list[BarItem]:
    """기준 시공상세도 ↔ 가공도 (일치 시나리오)."""
    return [
        BarItem(mark="B1", diameter=16, length_mm=2400, count=20, bend_type="ㄱ", grade="SD400"),
        BarItem(mark="B2", diameter=13, length_mm=2400, count=40, bend_type="-", grade="SD400"),
        BarItem(mark="S1", diameter=10, length_mm=1800, count=60, bend_type="-", grade="SD400"),
        BarItem(mark="S2", diameter=10, length_mm=1500, count=80, bend_type="-", grade="SD400"),
        BarItem(mark="M1", diameter=22, length_mm=3500, count=12, bend_type="-", grade="SD500"),
    ]


def mismatched_invoice_items() -> list[BarItem]:
    """송장 B: D13 절반 누락 + D22 5개 부족 (불일치 시나리오)."""
    return [
        BarItem(mark="B1", diameter=16, length_mm=2400, count=20),
        BarItem(mark="B2", diameter=13, length_mm=2400, count=20),  # 40 → 20
        BarItem(mark="S1", diameter=10, length_mm=1800, count=60),
        BarItem(mark="S2", diameter=10, length_mm=1500, count=80),
        BarItem(mark="M1", diameter=22, length_mm=3500, count=7),  # 12 → 7
    ]


def write_bbs_excel(items: list[BarItem], out: Path) -> None:
    """가공도(BBS) 형식 Excel: 부호/직경/단위길이/개수/형상 컬럼."""
    wb = Workbook()
    ws = wb.active
    ws.title = "BBS"
    ws.append(["번호", "부호", "직경", "단위길이", "개수", "형상", "재질"])
    for idx, it in enumerate(items, start=1):
        ws.append([idx, it.mark, f"D{it.diameter}", it.length_mm, it.count, it.bend_type, it.grade])
    wb.save(out)


def write_invoice_excel(items: list[BarItem], out: Path) -> None:
    """반입 송장 Excel: 품명/규격/길이/수량 (부호 없을 수 있음)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "송장"
    ws.append(["품명", "규격", "길이", "수량"])
    for it in items:
        ws.append([f"이형철근 {it.grade or ''}".strip(), f"D{it.diameter}", it.length_mm, it.count])
    wb.save(out)


def write_invoice_pdf(items: list[BarItem], out: Path) -> None:
    """송장 PDF (pdfplumber로 다시 읽을 수 있도록 reportlab으로 그리지 않고
    간단한 표 텍스트를 fpdf 대신 PIL+pdfplumber 호환을 위해 reportlab으로 작성).

    여기서는 외부 의존을 늘리지 않기 위해 pdf를 만들지 않고
    Excel을 PDF로 가장하는 방식 대신, 단순 텍스트 PDF를 만든다.
    """
    # reportlab은 표 렌더에 가장 안정적. 이미 환경에 없을 수 있으므로
    # 동적 import 후 누락 시 에러 메시지로 안내.
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    except ImportError as e:
        raise RuntimeError(
            "PDF 더미 생성에는 reportlab 패키지가 필요합니다. uv add reportlab"
        ) from e

    # 한글 폰트가 없으면 영문/숫자만 쓰는 헤더로 처리 (pdfplumber는 텍스트 그대로 읽음).
    font_name = "Helvetica"
    for candidate in (
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).exists():
            try:
                pdfmetrics.registerFont(TTFont("BodyFont", candidate))
                font_name = "BodyFont"
                break
            except Exception:
                pass

    doc = SimpleDocTemplate(str(out), pagesize=A4)
    data = [["NAME", "SPEC", "LENGTH", "QTY"]]
    for it in items:
        data.append(
            [
                "Deformed Bar",
                f"D{it.diameter}",
                str(it.length_mm),
                str(it.count),
            ]
        )
    table = Table(data, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), font_name, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ]
        )
    )
    doc.build([table])


def write_drawing_dxf(items: list[BarItem], out: Path) -> None:
    """시공상세도 DXF: 각 부호를 INSERT+ATTRIB 형태로 배치."""
    doc = ezdxf.new(dxfversion="R2018")
    block_name = "REBAR_TAG"
    if block_name not in doc.blocks:
        block = doc.blocks.new(name=block_name)
        block.add_attdef("MARK", (0, 0), dxfattribs={"height": 2.5})
        block.add_attdef("DIA", (0, -3), dxfattribs={"height": 2.5})
        block.add_attdef("LEN", (0, -6), dxfattribs={"height": 2.5})
        block.add_attdef("CNT", (0, -9), dxfattribs={"height": 2.5})

    msp = doc.modelspace()
    for idx, it in enumerate(items):
        insert = msp.add_blockref(
            block_name,
            insert=(idx * 30, 0),
            dxfattribs={"xscale": 1.0, "yscale": 1.0},
        )
        insert.add_auto_attribs(
            {
                "MARK": it.mark or "",
                "DIA": f"D{it.diameter}",
                "LEN": str(it.length_mm),
                "CNT": str(it.count),
            }
        )
    doc.saveas(out)


def generate_all(out_dir: str | Path) -> dict[str, Path]:
    """모든 더미 파일을 생성하고 경로 사전 반환."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ref = reference_items()
    mis = mismatched_invoice_items()
    paths: dict[str, Path] = {
        "bbs_xlsx": out / "bbs_drawing.xlsx",
        "invoice_match_xlsx": out / "invoice_match.xlsx",
        "invoice_mismatch_xlsx": out / "invoice_mismatch.xlsx",
        "drawing_dxf": out / "drawing.dxf",
    }
    write_bbs_excel(ref, paths["bbs_xlsx"])
    write_invoice_excel(ref, paths["invoice_match_xlsx"])
    write_invoice_excel(mis, paths["invoice_mismatch_xlsx"])
    write_drawing_dxf(ref, paths["drawing_dxf"])
    # PDF는 reportlab 의존성이 있을 때만 생성
    try:
        pdf_path = out / "invoice_match.pdf"
        write_invoice_pdf(ref, pdf_path)
        paths["invoice_match_pdf"] = pdf_path
    except RuntimeError:
        pass
    return paths
