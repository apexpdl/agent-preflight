"""
ATF Dashboard — FastAPI-powered monitoring UI.

Displays real-time pipeline activity, risk charts, passport logs,
mirror diffs, and policy violations. Basic HTML templates — no
heavy frontend framework required.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from agent_preflight.atf.config import ATFConfig
from agent_preflight.atf.database import ATFDatabase

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"


def _render_template(name: str, **kwargs) -> str:
    """Simple template rendering with string substitution."""
    template_path = _TEMPLATE_DIR / name
    content = template_path.read_text()
    for key, value in kwargs.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))
    return content


def create_dashboard_app(config: Optional[ATFConfig] = None):
    """Create the ATF Dashboard FastAPI application."""
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, FileResponse
    except ImportError:
        raise ImportError(
            "FastAPI required for dashboard. Install: pip install agent-preflight[server]"
        )

    cfg = config or ATFConfig()
    db = ATFDatabase(cfg.database_path)
    app = FastAPI(title="ATF Dashboard", version="1.0.0")

    @app.on_event("startup")
    async def startup():
        await db.initialize()

    @app.get("/", response_class=HTMLResponse)
    async def index():
        stats = await db.get_stats()
        recent_logs = await db.get_pipeline_logs(limit=20)
        passports = await db.get_passports(limit=10)

        # Build timeline rows (table + visual flow)
        timeline_html = ""
        for log in recent_logs:
            verdict_class = {
                "allow": "verdict-allow",
                "warn": "verdict-warn",
                "block": "verdict-block",
                "require_approval": "verdict-warn",
            }.get(log["verdict"], "")
            risk_bar_width = int(log["risk_score"] * 100)

            # Visual flow: Agent -> Tool -> Risk -> Verdict
            verdict_icon = {"allow": "&#10003;", "warn": "&#9888;", "block": "&#9940;",
                           "require_approval": "&#128274;"}.get(log["verdict"], "?")
            dot_class = {"allow": "dot-green", "warn": "dot-yellow",
                        "block": "dot-red", "require_approval": "dot-yellow"}.get(log["verdict"], "")

            timeline_html += f"""
            <div class="timeline-entry {verdict_class}">
                <div class="timeline-dot {dot_class}"></div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-agent">{log['agent_id']}</span>
                        <span class="timeline-time">{log['created_at']}</span>
                    </div>
                    <div class="timeline-flow">
                        <span class="flow-step">Agent</span>
                        <span class="flow-arrow">&rarr;</span>
                        <span class="flow-step flow-tool">{log['tool_name']}</span>
                        <span class="flow-arrow">&rarr;</span>
                        <span class="flow-step flow-risk">Risk {log['risk_score']:.2f}</span>
                        <span class="flow-arrow">&rarr;</span>
                        <span class="flow-step flow-verdict {verdict_class}">{verdict_icon} {log['verdict'].upper()}</span>
                    </div>
                    <div class="timeline-meta">{log.get('pipeline_time_ms', 0):.0f}ms pipeline</div>
                </div>
            </div>"""

        # Build passport rows
        passport_html = ""
        for p in passports:
            passport_html += f"""
            <tr>
                <td><code title="{p['passport_id']}">{p['passport_id'][:12]}...</code></td>
                <td><code>{p['agent_id']}</code></td>
                <td><code>{p['tool_name']}</code></td>
                <td>{p['risk_score']:.2f}</td>
                <td>{p['policy_status']}</td>
                <td>{'Yes' if p.get('mirror_executed') else 'No'}</td>
                <td><code title="{p['signature']}">{p['signature'][:16]}...</code></td>
            </tr>"""

        return _render_index(stats, timeline_html, passport_html)

    @app.get("/static/style.css")
    async def serve_css():
        return FileResponse(_STATIC_DIR / "style.css", media_type="text/css")

    @app.get("/api/logs")
    async def api_logs(limit: int = 100, verdict: Optional[str] = None):
        logs = await db.get_pipeline_logs(limit=limit, verdict=verdict)
        return {"logs": logs}

    @app.get("/api/passports")
    async def api_passports(limit: int = 50):
        passports = await db.get_passports(limit=limit)
        return {"passports": passports}

    @app.get("/api/stats")
    async def api_stats():
        return await db.get_stats()

    return app


def _render_index(stats: dict, timeline_html: str, passport_html: str) -> str:
    """Render the main dashboard page."""
    block_rate_pct = f"{stats.get('block_rate', 0) * 100:.1f}"
    avg_risk = f"{stats.get('average_risk_score', 0):.3f}"
    avg_time = f"{stats.get('average_pipeline_time_ms', 0):.0f}"
    total = stats.get("total_actions", 0)
    blocked = stats.get("blocked_actions", 0)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ATF Dashboard — Agent Preflight</title>
    <link rel="stylesheet" href="/static/style.css">
    <meta http-equiv="refresh" content="10">
</head>
<body>
    <header>
        <h1>Agent Preflight — Autonomous Trust Fabric</h1>
        <p class="subtitle">Real-time AI Agent Governance Dashboard</p>
    </header>

    <section class="stats-grid">
        <div class="stat-card">
            <div class="stat-value">{total}</div>
            <div class="stat-label">Total Actions</div>
        </div>
        <div class="stat-card stat-danger">
            <div class="stat-value">{blocked}</div>
            <div class="stat-label">Blocked</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{block_rate_pct}%</div>
            <div class="stat-label">Block Rate</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{avg_risk}</div>
            <div class="stat-label">Avg Risk Score</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{avg_time}ms</div>
            <div class="stat-label">Avg Pipeline Time</div>
        </div>
    </section>

    <section class="panel">
        <h2>Action Timeline</h2>
        <table>
            <thead>
                <tr>
                    <th>Timestamp</th>
                    <th>Agent</th>
                    <th>Tool</th>
                    <th>Risk Score</th>
                    <th>Verdict</th>
                    <th>Time</th>
                </tr>
            </thead>
            <tbody>
                {timeline_html if timeline_html else '<tr><td colspan="6" class="empty">No actions recorded yet</td></tr>'}
            </tbody>
        </table>
    </section>

    <section class="panel">
        <h2>Visual Agent Timeline</h2>
        <div class="agent-timeline">
            {timeline_html if timeline_html else '<p class="empty">No actions recorded yet</p>'}
        </div>
        <p class="timeline-legend">
            <span class="legend-item"><span class="dot dot-green"></span> Allowed</span>
            <span class="legend-item"><span class="dot dot-yellow"></span> Warning</span>
            <span class="legend-item"><span class="dot dot-red"></span> Blocked</span>
        </p>
    </section>

    <section class="panel">
        <h2>Action Passports</h2>
        <table>
            <thead>
                <tr>
                    <th>Passport ID</th>
                    <th>Agent</th>
                    <th>Tool</th>
                    <th>Risk</th>
                    <th>Policy</th>
                    <th>Mirror</th>
                    <th>Signature</th>
                </tr>
            </thead>
            <tbody>
                {passport_html if passport_html else '<tr><td colspan="7" class="empty">No passports issued yet</td></tr>'}
            </tbody>
        </table>
    </section>

    <footer>
        <p>Agent Preflight ATF v1.0 — Predictive Consequence Infrastructure for Autonomous Systems</p>
    </footer>
</body>
</html>"""
