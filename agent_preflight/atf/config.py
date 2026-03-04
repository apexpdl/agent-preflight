"""
ATF configuration with sensible defaults and per-mode tuning.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from agent_preflight.atf.models import ExecutionMode


class ATFConfig(BaseModel):
    """Central configuration for the Autonomous Trust Fabric."""

    # Operating mode
    mode: ExecutionMode = ExecutionMode.SAFE

    # Risk thresholds (0.0 - 1.0)
    risk_threshold_mirror: float = Field(default=0.5, ge=0.0, le=1.0)
    risk_threshold_block: float = Field(default=0.8, ge=0.0, le=1.0)

    # Simulation
    simulation_rollouts: int = Field(default=50, ge=1, le=10000)
    simulation_enabled: bool = True

    # Mirror World
    mirror_enabled: bool = True
    mirror_timeout_seconds: float = 5.0

    # Drift Intelligence
    drift_enabled: bool = True
    drift_anomaly_threshold: float = 0.7

    # Passport signing
    passport_secret_key: str = Field(
        default_factory=lambda: os.environ.get("ATF_PASSPORT_SECRET", "change-me-in-production")
    )

    # Database
    database_path: Path = Field(default=Path("./atf_data.db"))

    # Policy
    policy_file: Optional[Path] = None

    # Federation (optional)
    federation_enabled: bool = False
    federation_endpoint: Optional[str] = None

    # Logging
    log_level: str = "INFO"
    structured_logging: bool = True

    # Performance
    max_pipeline_time_ms: float = 800.0

    @classmethod
    def for_mode(cls, mode: ExecutionMode, **overrides) -> ATFConfig:
        """Get config tuned for a specific operating mode."""
        presets: dict[ExecutionMode, dict] = {
            ExecutionMode.SAFE: {
                "risk_threshold_mirror": 0.3,
                "risk_threshold_block": 0.6,
                "simulation_rollouts": 100,
                "mirror_enabled": True,
            },
            ExecutionMode.BALANCED: {
                "risk_threshold_mirror": 0.5,
                "risk_threshold_block": 0.8,
                "simulation_rollouts": 50,
                "mirror_enabled": True,
            },
            ExecutionMode.AGGRESSIVE: {
                "risk_threshold_mirror": 0.7,
                "risk_threshold_block": 0.9,
                "simulation_rollouts": 20,
                "mirror_enabled": False,
            },
            ExecutionMode.ENTERPRISE: {
                "risk_threshold_mirror": 0.3,
                "risk_threshold_block": 0.5,
                "simulation_rollouts": 200,
                "mirror_enabled": True,
                "drift_enabled": True,
                "structured_logging": True,
            },
        }
        params = {"mode": mode, **presets.get(mode, {}), **overrides}
        return cls(**params)
