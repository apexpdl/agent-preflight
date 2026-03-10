from __future__ import annotations

import os
from dataclasses import dataclass, field

from agent_preflight.atf.models import ExecutionMode


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes")


def _parse_origins(value: str) -> list[str]:
    return [o.strip() for o in value.split(",") if o.strip()]


@dataclass(frozen=True)
class DemoConfig:
    demo_mode: bool = field(
        default_factory=lambda: _parse_bool(os.environ.get("DEMO_MODE", "true"))
    )
    cors_origins: list[str] = field(
        default_factory=lambda: _parse_origins(
            os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
        )
    )
    atf_passport_secret: str = field(
        default_factory=lambda: os.environ.get("ATF_PASSPORT_SECRET", "demo-secret-change-me")
    )
    port: int = field(
        default_factory=lambda: int(os.environ.get("PORT", "8100"))
    )
    rate_limit_rpm: int = field(
        default_factory=lambda: int(os.environ.get("RATE_LIMIT_RPM", "30"))
    )
    max_payload_bytes: int = field(
        default_factory=lambda: int(os.environ.get("MAX_PAYLOAD_BYTES", "10240"))
    )
    log_level: str = field(
        default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO").upper()
    )
    atf_mode: ExecutionMode = field(
        default_factory=lambda: ExecutionMode(os.environ.get("ATF_MODE", "balanced"))
    )
