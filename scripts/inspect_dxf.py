"""DXF 도면들의 텍스트 패턴과 부호 분포를 일괄 조사."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import ezdxf

# 부호로 추정할 텍스트 패턴 (예: F1, F4A, WF1, RPW1, S1, B12, P1A 등)
MARK_RE = re.compile(r"^[A-Z]{1,5}[\s-]?\d{1,3}[A-Z]?$")
# 노이즈로 제거할 텍스트
NOISE_PATTERNS = (
    re.compile(r"^\d+(\.\d+)?$"),  # 순수 숫자
    re.compile(r"^[%@&\-=]+$"),
    re.compile(r"^(NONE|fck|fy|MPa|D|@|mm|cm|m)$", re.IGNORECASE),
)


def is_mark_like(text: str) -> bool:
    t = text.strip()
    if not t or len(t) > 12:
        return False
    if any(p.match(t) for p in NOISE_PATTERNS):
        return False
    return bool(MARK_RE.match(t))


def inspect(path: Path) -> dict:
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    types = Counter(e.dxftype() for e in msp)

    texts = list(msp.query("TEXT"))
    mtexts = list(msp.query("MTEXT"))
    text_strings = [t.dxf.text.strip() for t in texts if t.dxf.text.strip()]
    mtext_strings: list[str] = []
    for m in mtexts:
        s = m.plain_text() if hasattr(m, "plain_text") else str(m.dxf.text)
        s = s.strip()
        if s:
            mtext_strings.append(s)
    all_texts = text_strings + mtext_strings

    mark_candidates = Counter(t for t in all_texts if is_mark_like(t))

    inserts = list(msp.query("INSERT"))
    block_names = Counter(ins.dxf.name for ins in inserts)
    attribs_seen: list[tuple[str, ...]] = []
    for ins in inserts[:300]:
        tags = tuple(a.dxf.tag for a in ins.attribs)
        if tags:
            attribs_seen.append(tags)
    attrib_signatures = Counter(attribs_seen)

    return {
        "path": str(path),
        "version": doc.dxfversion,
        "encoding": doc.encoding,
        "entity_counts": types,
        "n_text": len(texts),
        "n_mtext": len(mtexts),
        "mark_candidates_top": mark_candidates.most_common(40),
        "n_unique_marks": len(mark_candidates),
        "n_total_marks": sum(mark_candidates.values()),
        "block_names_top": block_names.most_common(10),
        "attrib_signatures": attrib_signatures.most_common(5),
    }


def main() -> None:
    files = sorted(Path("samples").glob("*.dxf"))
    files = [f for f in files if f.name != "drawing.dxf"]
    for f in files:
        print(f"\n{'=' * 80}\n파일: {f.name}  ({f.stat().st_size / 1024 / 1024:.1f} MB)")
        try:
            r = inspect(f)
        except Exception as e:
            print(f"  실패: {e}")
            continue
        print(f"  버전: {r['version']}, 인코딩: {r['encoding']}")
        print(f"  TEXT={r['n_text']}, MTEXT={r['n_mtext']}")
        print(f"  엔티티: {dict(r['entity_counts'].most_common(6))}")
        print(f"  부호 후보 — 종류 {r['n_unique_marks']}개, 총 {r['n_total_marks']}회 출현")
        if r["mark_candidates_top"]:
            print("  상위 20개:")
            for mark, count in r["mark_candidates_top"][:20]:
                print(f"    {count:>4d}  {mark!r}")
        if r["attrib_signatures"]:
            print(f"  ATTRIB 시그니처: {r['attrib_signatures']}")


if __name__ == "__main__":
    sys.exit(main())
