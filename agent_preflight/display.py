"""
Interceptor display — screenshot-worthy terminal output for ATF verdicts.

Designed to be the first thing a user sees when Preflight blocks something.
Clean. Professional. Dramatic. Screenshot-ready.
"""

from __future__ import annotations

import sys
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from agent_preflight.atf.models import PipelineResult


# ---------------------------------------------------------------------------
# ANSI codes (with graceful degradation)
# ---------------------------------------------------------------------------

def _supports_color() -> bool:
    if not hasattr(sys.stdout, "isatty"):
        return False
    if not sys.stdout.isatty():
        return False
    return True


class _S:
    """Style codes — degrade gracefully on non-TTY."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


class _NoColor:
    """No-op style codes for non-TTY environments."""
    def __getattr__(self, name):
        return ""

_s = _S() if _supports_color() else _NoColor()


# ---------------------------------------------------------------------------
# Box-drawing characters
# ---------------------------------------------------------------------------

_TOP = "━"
_PIPE = "│"
_DOT = "●"


def _bar(width: int = 58) -> str:
    return f"{_s.DIM}{_TOP * width}{_s.RESET}"


def _risk_color(score: float) -> str:
    if score >= 0.8:
        return _s.RED
    elif score >= 0.5:
        return _s.YELLOW
    elif score >= 0.3:
        return _s.BLUE
    return _s.GREEN


def _risk_label(score: float) -> str:
    if score >= 0.8:
        return "Critical"
    elif score >= 0.5:
        return "High"
    elif score >= 0.3:
        return "Medium"
    return "Low"


def _risk_meter(score: float, width: int = 20) -> str:
    """Visual risk meter: [████████░░░░░░░░░░░░] 87%"""
    filled = int(score * width)
    empty = width - filled
    color = _risk_color(score)
    bar = f"{color}{'█' * filled}{_s.DIM}{'░' * empty}{_s.RESET}"
    pct = f"{score:.0%}"
    return f"{bar} {color}{_s.BOLD}{pct}{_s.RESET}"


def _verdict_display(verdict: str) -> str:
    v = verdict.upper()
    if v == "BLOCK":
        return f"{_s.BG_RED}{_s.WHITE}{_s.BOLD} BLOCKED {_s.RESET}"
    elif v == "WARN":
        return f"{_s.BG_YELLOW}{_s.BOLD} WARNING {_s.RESET}"
    elif v == "ALLOW":
        return f"{_s.BG_GREEN}{_s.BOLD} ALLOWED {_s.RESET}"
    elif v == "REQUIRE_APPROVAL":
        return f"{_s.BG_BLUE}{_s.WHITE}{_s.BOLD} NEEDS APPROVAL {_s.RESET}"
    return f"{_s.BOLD} {v} {_s.RESET}"


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_interception(
    tool_name: str,
    verdict: str,
    risk_score: float,
    flags: list[str],
    human_summary: str = "",
    correction: Optional[dict] = None,
    pipeline_time_ms: float = 0,
    passport_id: str = "",
    simulation: Optional[dict] = None,
) -> str:
    """Render a screenshot-worthy interception display.

    This is what users see in their terminal when Preflight
    intercepts an action. Designed to be impressive on first run.
    """
    lines: list[str] = []
    W = 58

    lines.append("")
    lines.append(_bar(W))

    # Header with verdict icon
    if verdict.upper() == "BLOCK":
        icon = f"{_s.RED}⛔{_s.RESET}"
    elif verdict.upper() == "WARN":
        icon = f"{_s.YELLOW}⚠{_s.RESET}"
    else:
        icon = f"{_s.GREEN}✓{_s.RESET}"

    lines.append(f"  {icon}  {_s.BOLD}PREFLIGHT{_s.RESET} {_verdict_display(verdict)}")
    lines.append(_bar(W))

    # Tool
    lines.append(f"  {_s.DIM}Tool:{_s.RESET}    {_s.BOLD}{tool_name}{_s.RESET}")

    # Risk meter
    lines.append(f"  {_s.DIM}Risk:{_s.RESET}    {_risk_meter(risk_score)}")

    # Flags (compact)
    if flags:
        readable = [f.replace("_", " ") for f in flags[:4]]
        lines.append(f"  {_s.DIM}Flags:{_s.RESET}   {_risk_color(risk_score)}{', '.join(readable)}{_s.RESET}")

    # Summary
    if human_summary:
        # Wrap summary to fit
        summary_text = human_summary
        if len(summary_text) > 100:
            summary_text = summary_text[:97] + "..."
        lines.append(f"  {_s.DIM}Reason:{_s.RESET}  {summary_text}")

    # Simulation results (compact)
    if simulation:
        fail_p = simulation.get("failure_probability", 0)
        cascade = simulation.get("cascade_risk", 0)
        if fail_p > 0.1 or cascade > 0.1:
            lines.append(
                f"  {_s.DIM}Sim:{_s.RESET}     "
                f"{_s.YELLOW}{fail_p:.0%} failure{_s.RESET}"
                f"{_s.DIM} | {_s.RESET}"
                f"{_s.YELLOW}{cascade:.0%} cascade{_s.RESET}"
            )

    # Correction (only for blocks)
    if correction and verdict.upper() == "BLOCK":
        suggestions = correction.get("suggestions", [])
        if suggestions:
            lines.append(f"  {_s.DIM}{'─' * (W - 4)}{_s.RESET}")
            lines.append(f"  {_s.CYAN}{_s.BOLD}Suggested fix:{_s.RESET}")
            for s in suggestions[:3]:
                # Truncate long suggestions
                if len(s) > 52:
                    s = s[:49] + "..."
                lines.append(f"    {_s.CYAN}→ {s}{_s.RESET}")

    # Footer
    lines.append(_bar(W))
    footer_parts = []
    if pipeline_time_ms > 0:
        footer_parts.append(f"{pipeline_time_ms:.0f}ms")
    if passport_id:
        footer_parts.append(f"passport:{passport_id[:8]}")
    if footer_parts:
        lines.append(f"  {_s.DIM}{' │ '.join(footer_parts)}{_s.RESET}")

    lines.append("")
    return "\n".join(lines)


def render_pipeline_result(result: "PipelineResult") -> str:
    """Render a PipelineResult into the interceptor display."""
    sim_data = None
    if result.simulation_result:
        sim_data = {
            "failure_probability": result.simulation_result.failure_probability,
            "cascade_risk": result.simulation_result.cascade_probability,
        }

    correction_data = None
    if result.correction:
        correction_data = result.correction.model_dump()

    return render_interception(
        tool_name=result.action_id,  # Will be overridden by caller
        verdict=result.verdict.value,
        risk_score=result.risk_assessment.score,
        flags=result.risk_assessment.flags,
        human_summary=result.human_summary,
        correction=correction_data,
        pipeline_time_ms=result.total_pipeline_time_ms,
        passport_id=result.passport.passport_id if result.passport else "",
        simulation=sim_data,
    )


def render_startup_banner() -> str:
    """Render the startup banner shown when Preflight activates."""
    lines = [
        "",
        f"  {_s.BOLD}{_s.CYAN}▲ Preflight{_s.RESET}{_s.DIM} enabled — AI safety interception active{_s.RESET}",
        "",
    ]
    return "\n".join(lines)


def render_stats(stats: dict) -> str:
    """Render compact stats display."""
    total = stats.get("total", 0)
    blocked = stats.get("blocked", 0)
    warned = stats.get("warned", 0)
    allowed = stats.get("allowed", 0)

    lines = [
        "",
        _bar(40),
        f"  {_s.BOLD}Preflight Session Stats{_s.RESET}",
        _bar(40),
        f"  {_s.GREEN}{_DOT}{_s.RESET} Allowed:  {allowed}",
        f"  {_s.YELLOW}{_DOT}{_s.RESET} Warned:   {warned}",
        f"  {_s.RED}{_DOT}{_s.RESET} Blocked:  {blocked}",
        f"  {_s.DIM}  Total:   {total}{_s.RESET}",
        _bar(40),
        "",
    ]
    return "\n".join(lines)
