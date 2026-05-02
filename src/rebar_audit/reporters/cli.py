"""CLI 콘솔 리포트 (rich)."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rebar_audit.matcher import DiameterDiff, MarkDiff
from rebar_audit.models import RebarSet

_STATUS_STYLE = {
    "ok": ("[green]일치[/green]", "green"),
    "warning": ("[yellow]경고[/yellow]", "yellow"),
    "error": ("[red]불일치[/red]", "red"),
    "missing_a": ("[red]A 누락[/red]", "red"),
    "missing_b": ("[red]B 누락[/red]", "red"),
}


def _status_label(status: str) -> str:
    return _STATUS_STYLE.get(status, (status, "white"))[0]


def render_summary(console: Console, a: RebarSet, b: RebarSet) -> None:
    table = Table(title="입력 요약", show_header=True, header_style="bold cyan")
    table.add_column("출처", style="bold")
    table.add_column("종류")
    table.add_column("파일")
    table.add_column("항목 수", justify="right")
    table.add_column("총 개수", justify="right")
    table.add_column("총 길이(m)", justify="right")
    table.add_column("총 중량(kg)", justify="right")
    for label, rs in (("A", a), ("B", b)):
        table.add_row(
            label,
            f"{rs.origin}/{rs.source_kind}",
            rs.source_path,
            str(len(rs.items)),
            str(rs.total_count()),
            f"{rs.total_length_m():.2f}",
            f"{rs.total_weight_kg():.2f}",
        )
    console.print(table)


def render_stage1(console: Console, diffs: list[DiameterDiff], tol_pct: float) -> None:
    table = Table(
        title=f"Stage 1 — 직경별 총량 비교 (허용오차 ±{tol_pct}%)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("직경", justify="right")
    table.add_column("A 개수", justify="right")
    table.add_column("B 개수", justify="right")
    table.add_column("A 길이(m)", justify="right")
    table.add_column("B 길이(m)", justify="right")
    table.add_column("A 중량(kg)", justify="right")
    table.add_column("B 중량(kg)", justify="right")
    table.add_column("Δ중량(kg)", justify="right")
    table.add_column("Δ%", justify="right")
    table.add_column("상태")
    for d in diffs:
        table.add_row(
            f"D{d.diameter}",
            str(d.a_count),
            str(d.b_count),
            f"{d.a_length_m:.2f}",
            f"{d.b_length_m:.2f}",
            f"{d.a_weight_kg:.2f}",
            f"{d.b_weight_kg:.2f}",
            f"{d.weight_delta_kg:+.2f}",
            f"{d.weight_delta_pct:+.2f}",
            _status_label(d.status),
        )
    console.print(table)


def render_stage2(console: Console, diffs: list[MarkDiff]) -> None:
    if not diffs:
        console.print(
            Panel.fit(
                "Stage 2 — 부호별 1:1 대조: [yellow]스킵[/yellow] "
                "(한쪽 입력에 부호 컬럼이 없습니다. 송장에 부호 정보가 있으면 자동 활성화됩니다.)",
                border_style="yellow",
            )
        )
        return
    table = Table(title="Stage 2 — 부호별 1:1 대조", show_header=True, header_style="bold cyan")
    table.add_column("부호")
    table.add_column("A (직경/길이/개수)")
    table.add_column("B (직경/길이/개수)")
    table.add_column("상태")
    table.add_column("비고")
    for d in diffs:
        a_s = f"D{d.a.diameter}/{d.a.length_mm}/{d.a.count}" if d.a else "—"
        b_s = f"D{d.b.diameter}/{d.b.length_mm}/{d.b.count}" if d.b else "—"
        table.add_row(d.mark, a_s, b_s, _status_label(d.status), "; ".join(d.notes))
    console.print(table)


def render_verdict(console: Console, stage1: list[DiameterDiff], stage2: list[MarkDiff]) -> int:
    """전체 결과 판정. 반환값: 종료 코드 (0=일치, 1=경고, 2=오류)."""
    s1_errors = sum(1 for d in stage1 if d.status in ("error", "missing_a", "missing_b"))
    s1_warnings = sum(1 for d in stage1 if d.status == "warning")
    s2_errors = sum(1 for d in stage2 if d.status != "ok")
    code = 0
    if s1_errors or s2_errors:
        code = 2
    elif s1_warnings:
        code = 1

    color = {0: "green", 1: "yellow", 2: "red"}[code]
    label = {0: "최종: 일치", 1: "최종: 경고", 2: "최종: 불일치"}[code]
    detail = f"Stage1 오류 {s1_errors} / 경고 {s1_warnings}, Stage2 불일치 {s2_errors}"
    console.print(Panel.fit(f"[bold {color}]{label}[/bold {color}]\n{detail}", border_style=color))
    return code
