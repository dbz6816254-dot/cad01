"""Typer 기반 CLI 엔트리포인트.

사용:
    rebar-audit compare A.xlsx B.pdf --excel report.xlsx
    rebar-audit fixtures samples/
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from rebar_audit.matcher import compare_by_diameter, compare_by_mark
from rebar_audit.parsers import parse
from rebar_audit.reporters import excel as excel_report
from rebar_audit.reporters.cli import (
    render_stage1,
    render_stage2,
    render_summary,
    render_verdict,
)

app = typer.Typer(
    add_completion=False,
    help="철근 시공상세도/가공도 ↔ 송장 정합성 검증",
    no_args_is_help=True,
)


@app.command("compare")
def compare(
    a: Path = typer.Argument(..., exists=True, help="A 파일 (도면 또는 가공도)"),
    b: Path = typer.Argument(..., exists=True, help="B 파일 (송장 또는 가공도)"),
    a_origin: str = typer.Option("schedule", "--a-origin", help="drawing|schedule|invoice"),
    b_origin: str = typer.Option("invoice", "--b-origin", help="drawing|schedule|invoice"),
    tol_pct: float = typer.Option(2.0, "--tol", help="Stage1 직경별 중량 허용오차 ±%"),
    excel_out: Optional[Path] = typer.Option(  # noqa: UP045 (typer는 Optional 필요)
        None, "--excel", help="Excel 리포트 저장 경로"
    ),
) -> None:
    """A와 B 두 파일을 비교해 정합성 리포트 생성."""
    console = Console()
    rs_a = parse(a, origin=a_origin)  # type: ignore[arg-type]
    rs_b = parse(b, origin=b_origin)  # type: ignore[arg-type]

    render_summary(console, rs_a, rs_b)
    stage1 = compare_by_diameter(rs_a, rs_b, weight_tol_pct=tol_pct)
    stage2 = compare_by_mark(rs_a, rs_b)
    render_stage1(console, stage1, tol_pct=tol_pct)
    render_stage2(console, stage2)
    code = render_verdict(console, stage1, stage2)

    if excel_out:
        path = excel_report.write_report(excel_out, rs_a, rs_b, stage1, stage2)
        console.print(f"[cyan]Excel 리포트 저장:[/cyan] {path}")

    raise typer.Exit(code=code)


@app.command("fixtures")
def fixtures(
    out_dir: Path = typer.Argument(Path("samples"), help="더미 샘플을 저장할 디렉토리"),
) -> None:
    """더미 BBS/송장/DXF/PDF 샘플을 생성."""
    from rebar_audit.fixtures import generate_all

    paths = generate_all(out_dir)
    console = Console()
    console.print(f"[green]더미 샘플 생성 완료:[/green] {out_dir}")
    for k, v in paths.items():
        console.print(f"  - {k}: {v}")


if __name__ == "__main__":
    app()
