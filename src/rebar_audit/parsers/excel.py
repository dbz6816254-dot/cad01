"""Excel/CSV 파서. BBS(가공도) 또는 송장 표를 RebarSet으로 변환."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from rebar_audit.models import BarItem, Origin, RebarSet

# 컬럼 헤더 동의어 (소문자 비교)
HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "mark": ("부호", "기호", "철근부호", "품번", "no", "번호", "mark", "tag"),
    "diameter": ("직경", "규격", "호칭", "사양", "spec", "dia", "d", "φ"),
    "length": ("단위길이", "길이", "절단길이", "length", "len", "l"),
    "count": ("개수", "수량", "본수", "qty", "count", "ea"),
    "bend_type": ("형상", "가공형상", "shape"),
    "grade": ("강도", "등급", "재질", "grade"),
}


_DIAMETER_RE = re.compile(r"(\d{1,2})")


def _norm_header(s: str) -> str:
    return re.sub(r"\s+", "", str(s)).lower()


def _detect_columns(headers: list[str]) -> dict[str, str]:
    """원본 컬럼명 → 표준 필드명 매핑."""
    mapping: dict[str, str] = {}
    norm = {_norm_header(h): h for h in headers}
    for field, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            for nh, original in norm.items():
                if alias in nh and original not in mapping:
                    mapping[original] = field
                    break
            if any(v == field for v in mapping.values()):
                break
    return mapping


def _parse_diameter(v: object) -> int | None:
    """'D13', 'φ10', '13mm', 13.0 → 정수 mm."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v)
    m = _DIAMETER_RE.search(s)
    if not m:
        return None
    return int(m.group(1))


def _parse_int(v: object) -> int | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return int(float(str(v).replace(",", "")))
    except (ValueError, TypeError):
        return None


def _row_to_item(row: dict, col_map: dict[str, str]) -> BarItem | None:
    """표준 컬럼 매핑을 거쳐 한 행을 BarItem으로 변환. 실패 시 None."""
    field_values: dict[str, object] = {}
    for original, field in col_map.items():
        field_values[field] = row.get(original)

    diameter = _parse_diameter(field_values.get("diameter"))
    length = _parse_int(field_values.get("length"))
    count = _parse_int(field_values.get("count"))
    if diameter is None or length is None or count is None or count <= 0 or length <= 0:
        return None

    mark = field_values.get("mark")
    return BarItem(
        mark=str(mark) if mark is not None and not pd.isna(mark) else None,
        diameter=diameter,
        length_mm=length,
        count=count,
        bend_type=(
            str(field_values["bend_type"])
            if field_values.get("bend_type") is not None and not pd.isna(field_values["bend_type"])
            else None
        ),
        grade=(
            str(field_values["grade"])
            if field_values.get("grade") is not None and not pd.isna(field_values["grade"])
            else None
        ),
    )


def _read_table(path: Path, sheet: str | int = 0) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        return pd.read_excel(path, sheet_name=sheet, dtype=object)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=object)
    raise ValueError(f"지원하지 않는 표 포맷: {path.suffix}")


def parse_excel(
    path: str | Path,
    origin: Origin = "schedule",
    sheet: str | int = 0,
) -> RebarSet:
    """Excel/CSV 파일을 RebarSet으로 파싱.

    - origin='schedule': 가공도(BBS)
    - origin='invoice':  반입 송장 (부호 컬럼 없을 수 있음)
    """
    p = Path(path)
    df = _read_table(p, sheet=sheet)
    df.columns = [str(c) for c in df.columns]
    col_map = _detect_columns(list(df.columns))
    if "diameter" not in col_map.values():
        raise ValueError(f"직경 컬럼을 찾지 못했습니다: {list(df.columns)}")

    items: list[BarItem] = []
    for _, row in df.iterrows():
        item = _row_to_item(row.to_dict(), col_map)
        if item is not None:
            items.append(item)

    kind = "csv" if p.suffix.lower() == ".csv" else "excel"
    return RebarSet(source_path=str(p), source_kind=kind, origin=origin, items=items)
