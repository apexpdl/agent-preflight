"""Plan renderer - terraform-plan-style CLI output."""

from __future__ import annotations
from .models import Plan, ActionCapture, RiskLevel, Reversibility, ActionType


class _C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_RED = "\033[41m"


def _risk_color(risk: RiskLevel) -> str:
    return {
        RiskLevel.LOW: _C.GREEN,
        RiskLevel.MEDIUM: _C.YELLOW,
        RiskLevel.HIGH: _C.RED,
        RiskLevel.CRITICAL: _C.BG_RED + _C.WHITE,
    }.get(risk, _C.WHITE)


def _risk_icon(risk: RiskLevel) -> str:
    return {
        RiskLevel.LOW: "  ",
        RiskLevel.MEDIUM: "! ",
        RiskLevel.HIGH: "!!",
        RiskLevel.CRITICAL: "!!",
    }.get(risk, "  ")


def _rev_tag(rev: Reversibility) -> str:
    return {
        Reversibility.REVERSIBLE: f"{_C.GREEN}REVERSIBLE{_C.RESET}",
        Reversibility.IRREVERSIBLE: f"{_C.RED}{_C.BOLD}IRREVERSIBLE{_C.RESET}",
        Reversibility.PARTIAL: f"{_C.YELLOW}PARTIAL{_C.RESET}",
        Reversibility.UNKNOWN: f"{_C.DIM}UNKNOWN{_C.RESET}",
    }.get(rev, "")


def _type_tag(atype: ActionType) -> str:
    return {
        ActionType.READ: f"{_C.GREEN}READ{_C.RESET}",
        ActionType.WRITE: f"{_C.YELLOW}WRITE{_C.RESET}",
        ActionType.DELETE: f"{_C.RED}DELETE{_C.RESET}",
        ActionType.EXECUTE: f"{_C.CYAN}EXEC{_C.RESET}",
    }.get(atype, "")


def _trunc(s: str, n: int = 60) -> str:
    s = str(s)
    return s[:n-3] + "..." if len(s) > n else s


def render(plan: Plan, color: bool = True, width: int = 64) -> str:
    if not color:
        return render_plain(plan, width)

    lines = []
    bar = f"{_C.DIM}{'=' * width}{_C.RESET}"

    lines.append("")
    lines.append(bar)
    lines.append(
        f"  {_C.BOLD}{_C.CYAN}PREFLIGHT PLAN{_C.RESET}"
        f"    {_C.DIM}{len(plan.actions)} action(s){_C.RESET}"
    )
    if plan.task_description:
        lines.append(f"  {_C.DIM}{_trunc(plan.task_description, width - 4)}{_C.RESET}")
    lines.append(bar)

    if plan.warnings:
        lines.append("")
        for w in plan.warnings:
            lines.append(f"  {_C.YELLOW}{_C.BOLD}WARNING:{_C.RESET} {_C.YELLOW}{w}{_C.RESET}")

    for i, action in enumerate(plan.actions):
        lines.append("")
        rc = _risk_color(action.risk_level)
        icon = _risk_icon(action.risk_level)
        lines.append(
            f"  {rc}{icon}{_C.RESET} "
            f"{_C.BOLD}{i+1}. {action.name}{_C.RESET}"
            f"  [{_type_tag(action.action_type)}]"
            f"  [{_rev_tag(action.reversibility)}]"
        )
        all_args = {**action.args, **action.kwargs}
        if all_args:
            for key, val in all_args.items():
                lines.append(f"     {_C.DIM}{key}:{_C.RESET} {_trunc(repr(val), width - 12)}")
        for reason in action.risk_reasons:
            lines.append(f"     {_C.RED}> {reason}{_C.RESET}")
        if action.estimated_cost and action.estimated_cost > 0:
            lines.append(f"     {_C.DIM}est. cost: ${action.estimated_cost:.4f}{_C.RESET}")

    lines.append("")
    lines.append(bar)
    rc = _risk_color(plan.overall_risk)
    lines.append(
        f"  {_C.BOLD}Risk:{_C.RESET}  "
        f"{rc}{_C.BOLD}{plan.overall_risk.value}{_C.RESET}"
        f"  {_C.DIM}({plan.irreversible_count} irreversible){_C.RESET}"
    )
    lines.append(f"  {_C.BOLD}Cost:{_C.RESET}  ${plan.total_estimated_cost:.4f} estimated")
    lines.append(f"  {_C.BOLD}Actions:{_C.RESET} {len(plan.actions)} total")
    lines.append(bar)
    lines.append("")
    return "\n".join(lines)


def render_plain(plan: Plan, width: int = 64) -> str:
    lines = []
    bar = "=" * width

    lines.append("")
    lines.append(bar)
    lines.append(f"  PREFLIGHT PLAN    {len(plan.actions)} action(s)")
    if plan.task_description:
        lines.append(f"  {_trunc(plan.task_description, width - 4)}")
    lines.append(bar)

    if plan.warnings:
        lines.append("")
        for w in plan.warnings:
            lines.append(f"  WARNING: {w}")

    for i, action in enumerate(plan.actions):
        lines.append("")
        icon = _risk_icon(action.risk_level)
        lines.append(
            f"  {icon} {i+1}. {action.name}"
            f"  [{action.action_type.value}]"
            f"  [{action.reversibility.value}]"
        )
        all_args = {**action.args, **action.kwargs}
        if all_args:
            for key, val in all_args.items():
                lines.append(f"     {key}: {_trunc(repr(val), width - 12)}")
        for reason in action.risk_reasons:
            lines.append(f"     > {reason}")
        if action.estimated_cost and action.estimated_cost > 0:
            lines.append(f"     est. cost: ${action.estimated_cost:.4f}")

    lines.append("")
    lines.append(bar)
    lines.append(f"  Risk:    {plan.overall_risk.value}  ({plan.irreversible_count} irreversible)")
    lines.append(f"  Cost:    ${plan.total_estimated_cost:.4f} estimated")
    lines.append(f"  Actions: {len(plan.actions)} total")
    lines.append(bar)
    lines.append("")
    return "\n".join(lines)
