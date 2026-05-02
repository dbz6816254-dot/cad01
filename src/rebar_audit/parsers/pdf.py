"""PDF 송장 파서 (pdfplumber)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pdfplumber

from rebar_audit.models import BarItem, Origin, RebarSet
from rebar_audit.parsers.excel import _detect_columns, _row_to_item


def parse_pdf(path: str | Path, origin: Origin = "invoice") -> RebarSet:
    """PDF의 모든 페이지에서 표를 추출해 RebarSet으로 결합.

    표 구조: 첫 번째 행을 헤더로 가정. 헤더 동의어는 excel 파서와 공유.
    """
    p = Path(path)
    items: list[BarItem] = []

    with pdfplumber.open(p) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                if not table or len(table) < 2:
                    continue
                header = [str(c) if c is not None else "" for c in table[0]]
                col_map = _detect_columns(header)
                if "diameter" not in col_map.values():
                    continue
                for row in table[1:]:
                    if not row or all(c is None or str(c).strip() == "" for c in row):
                        continue
                    row_dict = dict(zip(header, row, strict=False))
                    # pdfplumber 셀은 문자열, _row_to_item은 NaN 처리하므로 안전
                    item = _row_to_item(row_dict, col_map)
                    if item is not None:
                        items.append(item)

    if not items:
        # 보조 경로: 텍스트 추출 시 pandas로 한 번 더 시도
        text_items = _try_text_fallback(p)
        items.extend(text_items)

    return RebarSet(source_path=str(p), source_kind="pdf", origin=origin, items=items)


def _try_text_fallback(path: Path) -> list[BarItem]:
    """표 추출 실패 시 텍스트 라인을 공백 분리해 표로 재구성."""
    rows: list[list[str]] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                cells = [c for c in line.split() if c]
                if cells:
                    rows.append(cells)
    if len(rows) < 2:
        return []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    df = pd.DataFrame(rows[1:], columns=rows[0])
    col_map = _detect_columns(list(df.columns))
    if "diameter" not in col_map.values():
        return []
    items: list[BarItem] = []
    for _, row in df.iterrows():
        item = _row_to_item(row.to_dict(), col_map)
        if item is not None:
            items.append(item)
    return items
