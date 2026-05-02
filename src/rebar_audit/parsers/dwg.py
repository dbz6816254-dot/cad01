"""DWG 처리. ODA File Converter로 DXF 변환 후 DXF 파서에 위임."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from rebar_audit.models import Origin, RebarSet
from rebar_audit.parsers.dxf import parse_dxf

ODA_HINT = (
    "DWG 파일 처리에는 ODA File Converter(무료)가 필요합니다.\n"
    "  https://www.opendesign.com/guestfiles/oda_file_converter\n"
    "설치 후 'ODAFileConverter' 명령이 PATH에 있어야 합니다.\n"
    "또는 .dwg를 AutoCAD에서 .dxf로 직접 저장 후 사용해 주세요."
)


def _find_oda() -> str | None:
    for name in ("ODAFileConverter", "ODAFC", "oda-file-converter"):
        path = shutil.which(name)
        if path:
            return path
    return None


def parse_dwg(path: str | Path, origin: Origin = "drawing") -> RebarSet:
    """DWG → DXF 변환 후 DXF 파서로 위임. ODA 미설치 시 명확한 오류."""
    p = Path(path)
    converter = _find_oda()
    if converter is None:
        raise RuntimeError(ODA_HINT)

    with tempfile.TemporaryDirectory() as tmp_in, tempfile.TemporaryDirectory() as tmp_out:
        staged = Path(tmp_in) / p.name
        staged.write_bytes(p.read_bytes())
        # ODAFileConverter <input_dir> <output_dir> <ver> <type> <recursive> <audit> [filter]
        subprocess.run(
            [
                converter,
                tmp_in,
                tmp_out,
                "ACAD2018",
                "DXF",
                "0",
                "1",
                "*.DWG",
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        dxf_path = Path(tmp_out) / p.with_suffix(".dxf").name
        if not dxf_path.exists():
            raise RuntimeError(f"DWG → DXF 변환 산출물이 없습니다: {dxf_path}")
        rs = parse_dxf(dxf_path, origin=origin)
        # 출처 경로는 원본 DWG로 기록
        rs.source_path = str(p)
        rs.source_kind = "dwg"
        return rs
