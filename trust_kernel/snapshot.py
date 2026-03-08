"""
Preflight Safety Snapshot Generator.

Creates shareable, visual safety reports from pipeline execution data.
Generates HTML reports with embedded charts and a summary suitable
for social sharing (Slack, Twitter, LinkedIn).
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Any, Optional


class SafetySnapshot:
    """A shareable safety report from Preflight pipeline execution."""

    def __init__(
        self,
        snapshot_id: Optional[str] = None,
        tenant_id: str = "",
        period_label: str = "",
    ):
        self.snapshot_id = snapshot_id or secrets.token_urlsafe(16)
        self.tenant_id = tenant_id
        self.period_label = period_label or "Recent Activity"
        self.created_at = datetime.now(timezone.utc)

        # Aggregate stats
        self.total_actions: int = 0
        self.blocked_actions: int = 0
        self.warned_actions: int = 0
        self.allowed_actions: int = 0
        self.highest_risk_score: float = 0.0
        self.average_risk_score: float = 0.0
        self.total_cost_prevented: float = 0.0
        self.top_blocked_tools: list[dict[str, Any]] = []
        self.risk_distribution: dict[str, int] = {
            "low": 0, "medium": 0, "high": 0, "critical": 0,
        }
        self.pipeline_avg_ms: float = 0.0

    def add_action(
        self,
        verdict: str,
        risk_score: float,
        tool_name: str = "",
        cost_prevented: float = 0.0,
        pipeline_ms: float = 0.0,
    ) -> None:
        """Add an action result to the snapshot."""
        self.total_actions += 1

        if verdict == "block":
            self.blocked_actions += 1
            self.total_cost_prevented += cost_prevented
        elif verdict == "warn":
            self.warned_actions += 1
        else:
            self.allowed_actions += 1

        if risk_score > self.highest_risk_score:
            self.highest_risk_score = risk_score

        # Update running average
        n = self.total_actions
        self.average_risk_score = (
            (self.average_risk_score * (n - 1) + risk_score) / n
        )
        self.pipeline_avg_ms = (
            (self.pipeline_avg_ms * (n - 1) + pipeline_ms) / n
        )

        # Risk distribution
        if risk_score >= 0.8:
            self.risk_distribution["critical"] += 1
        elif risk_score >= 0.5:
            self.risk_distribution["high"] += 1
        elif risk_score >= 0.3:
            self.risk_distribution["medium"] += 1
        else:
            self.risk_distribution["low"] += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "period": self.period_label,
            "created_at": self.created_at.isoformat(),
            "total_actions": self.total_actions,
            "blocked": self.blocked_actions,
            "warned": self.warned_actions,
            "allowed": self.allowed_actions,
            "block_rate": (
                self.blocked_actions / max(self.total_actions, 1)
            ),
            "highest_risk": round(self.highest_risk_score, 4),
            "average_risk": round(self.average_risk_score, 4),
            "cost_prevented": round(self.total_cost_prevented, 2),
            "risk_distribution": self.risk_distribution,
            "avg_pipeline_ms": round(self.pipeline_avg_ms, 2),
        }

    def generate_html(self) -> str:
        """Generate a shareable HTML safety report."""
        block_rate = self.blocked_actions / max(self.total_actions, 1) * 100
        low_pct = self.risk_distribution["low"] / max(self.total_actions, 1) * 100
        med_pct = self.risk_distribution["medium"] / max(self.total_actions, 1) * 100
        high_pct = self.risk_distribution["high"] / max(self.total_actions, 1) * 100
        crit_pct = self.risk_distribution["critical"] / max(self.total_actions, 1) * 100

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Preflight Safety Snapshot</title>
<meta property="og:title" content="Preflight Safety Report">
<meta property="og:description" content="Blocked {self.blocked_actions} risky AI actions. ${self.total_cost_prevented:,.0f} in potential damage prevented.">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0f;color:#e0e0e0;min-height:100vh;display:flex;align-items:center;justify-content:center}}
.card{{background:linear-gradient(145deg,#12121a,#1a1a2e);border:1px solid #2a2a4a;border-radius:16px;padding:40px;max-width:520px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,0.5)}}
.logo{{font-size:24px;font-weight:700;color:#6c63ff;margin-bottom:4px}}
.subtitle{{font-size:13px;color:#888;margin-bottom:24px}}
.stats{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:24px}}
.stat{{text-align:center;padding:16px;background:rgba(255,255,255,0.03);border-radius:10px;border:1px solid #2a2a4a}}
.stat-value{{font-size:28px;font-weight:700;color:#fff}}
.stat-label{{font-size:11px;color:#888;margin-top:4px;text-transform:uppercase;letter-spacing:1px}}
.blocked .stat-value{{color:#ff4444}}
.saved .stat-value{{color:#4caf50}}
.risk-bar{{height:8px;background:#1a1a2e;border-radius:4px;overflow:hidden;margin-top:16px;display:flex}}
.risk-bar .low{{background:#4caf50;width:{low_pct}%}}
.risk-bar .med{{background:#ffc107;width:{med_pct}%}}
.risk-bar .high{{background:#ff9800;width:{high_pct}%}}
.risk-bar .crit{{background:#ff4444;width:{crit_pct}%}}
.risk-legend{{display:flex;gap:12px;margin-top:8px;font-size:11px;color:#888}}
.risk-legend span::before{{content:'';display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:4px;vertical-align:middle}}
.risk-legend .l::before{{background:#4caf50}}
.risk-legend .m::before{{background:#ffc107}}
.risk-legend .h::before{{background:#ff9800}}
.risk-legend .c::before{{background:#ff4444}}
.footer{{margin-top:24px;text-align:center;font-size:11px;color:#555}}
.badge{{display:inline-block;background:#6c63ff;color:#fff;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;margin-top:16px}}
</style>
</head>
<body>
<div class="card">
<div class="logo">Preflight</div>
<div class="subtitle">Safety Snapshot &mdash; {self.period_label}</div>
<div class="stats">
<div class="stat">
<div class="stat-value">{self.total_actions}</div>
<div class="stat-label">Actions Evaluated</div>
</div>
<div class="stat blocked">
<div class="stat-value">{self.blocked_actions}</div>
<div class="stat-label">Blocked</div>
</div>
<div class="stat saved">
<div class="stat-value">${self.total_cost_prevented:,.0f}</div>
<div class="stat-label">Cost Prevented</div>
</div>
</div>
<div style="font-size:13px;color:#aaa;margin-bottom:8px">Risk Distribution</div>
<div class="risk-bar">
<div class="low"></div>
<div class="med"></div>
<div class="high"></div>
<div class="crit"></div>
</div>
<div class="risk-legend">
<span class="l">Low {self.risk_distribution['low']}</span>
<span class="m">Medium {self.risk_distribution['medium']}</span>
<span class="h">High {self.risk_distribution['high']}</span>
<span class="c">Critical {self.risk_distribution['critical']}</span>
</div>
<div style="text-align:center">
<div class="badge">Block Rate: {block_rate:.1f}%</div>
</div>
<div class="footer">
Preflight Execution Firewall &bull; {self.created_at.strftime('%Y-%m-%d %H:%M UTC')}
<br>Snapshot ID: {self.snapshot_id}
</div>
</div>
</body>
</html>"""

    def generate_summary_text(self) -> str:
        """Generate a plain-text summary for social sharing."""
        block_rate = self.blocked_actions / max(self.total_actions, 1) * 100
        return (
            f"Preflight Safety Report\n"
            f"{'=' * 40}\n"
            f"Period: {self.period_label}\n"
            f"Total actions evaluated: {self.total_actions}\n"
            f"Blocked: {self.blocked_actions} ({block_rate:.1f}%)\n"
            f"Highest risk score: {self.highest_risk_score:.2f}\n"
            f"Cost prevented: ${self.total_cost_prevented:,.2f}\n"
            f"Avg pipeline time: {self.pipeline_avg_ms:.1f}ms\n"
            f"Snapshot ID: {self.snapshot_id}\n"
        )

    def generate_badge_svg(self) -> str:
        """Generate a shield-style SVG badge for repos."""
        if self.blocked_actions == 0 and self.total_actions > 0:
            color = "#4c1"
            status = "safe"
        elif self.blocked_actions / max(self.total_actions, 1) < 0.1:
            color = "#97ca00"
            status = "verified"
        else:
            color = "#dfb317"
            status = f"{self.blocked_actions} blocked"

        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="180" height="20">'
            f'<linearGradient id="a" x2="0" y2="100%">'
            f'<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
            f'<stop offset="1" stop-opacity=".1"/></linearGradient>'
            f'<rect rx="3" width="180" height="20" fill="#555"/>'
            f'<rect rx="3" x="80" width="100" height="20" fill="{color}"/>'
            f'<rect rx="3" width="180" height="20" fill="url(#a)"/>'
            f'<g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,sans-serif" font-size="11">'
            f'<text x="40" y="14">preflight</text>'
            f'<text x="130" y="14">{status}</text>'
            f'</g></svg>'
        )
