"""
Federation Protocol — data structures for inter-instance communication.

Only structural metadata is shared. No raw payloads, arguments, or
identifying information crosses the federation boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class FederatedSignal(BaseModel):
    """Anonymized action signal sent to the federation network."""
    action_fingerprint: str  # SHA-256 of canonical action structure
    risk_score: float
    verdict: str
    action_type: str
    tool_category: str  # Generalized: "filesystem", "api", "database", etc.
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    instance_id: str = ""  # Opaque identifier, not traceable


class GlobalStabilitySignal(BaseModel):
    """Aggregate intelligence received from the federation network."""
    action_fingerprint: str
    global_failure_rate: float = 0.0
    emerging_risk_flag: bool = False
    volatility_trend: str = "stable"  # stable, increasing, decreasing, spike
    sample_size: int = 0
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
