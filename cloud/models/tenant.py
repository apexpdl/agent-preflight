"""Tenant models for Preflight Cloud.

Pydantic v2 models that serve as the data layer. Zero-dependency core —
no SQLAlchemy required. Models serialize cleanly to SQL via .model_dump().
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TenantRole(str, Enum):
    """Roles within a tenant organization."""

    OWNER = "owner"
    OPERATOR = "operator"
    AUDITOR = "auditor"


class TenantSettings(BaseModel):
    """Per-tenant configuration for execution governance."""

    risk_threshold_block: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Risk score at or above which actions are blocked.",
    )
    risk_threshold_warn: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Risk score at or above which actions trigger a warning.",
    )
    max_actions_per_minute: int = Field(
        default=100,
        ge=1,
        description="Rate limit: maximum actions per minute.",
    )
    max_monthly_actions: int = Field(
        default=10_000,
        ge=0,
        description="Monthly action quota. 0 = unlimited.",
    )
    budget_limit_usd: float = Field(
        default=1000.0,
        ge=0.0,
        description="Monthly spend cap in USD.",
    )
    require_approval_above_risk: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Actions above this risk score require human approval.",
    )
    execution_mode: str = Field(
        default="balanced",
        description="Execution mode: strict, balanced, or permissive.",
    )
    passport_signing_enabled: bool = Field(
        default=True,
        description="Whether cryptographic passport signing is enabled.",
    )

    @field_validator("execution_mode")
    @classmethod
    def validate_execution_mode(cls, v: str) -> str:
        allowed = {"strict", "balanced", "permissive"}
        if v not in allowed:
            raise ValueError(f"execution_mode must be one of {allowed}")
        return v


class Tenant(BaseModel):
    """A tenant organization in Preflight Cloud."""

    tenant_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(
        ...,
        min_length=1,
        max_length=63,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
        description="URL-safe identifier for the tenant.",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    plan: str = Field(
        default="starter",
        description="Billing plan: starter, professional, or enterprise.",
    )
    settings: TenantSettings = Field(default_factory=TenantSettings)
    active: bool = True

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: str) -> str:
        allowed = {"starter", "professional", "enterprise"}
        if v not in allowed:
            raise ValueError(f"plan must be one of {allowed}")
        return v


class TenantUser(BaseModel):
    """A user within a tenant organization."""

    user_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    tenant_id: str
    email: str = Field(..., description="User email address.")
    role: TenantRole = TenantRole.OPERATOR
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: Optional[datetime] = None


class APIKey(BaseModel):
    """An API key for programmatic access to a tenant's resources."""

    key_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    tenant_id: str
    key_hash: str = Field(
        ...,
        description="bcrypt hash of the API key. Plaintext is never stored.",
    )
    name: str = Field(..., min_length=1, max_length=255)
    permissions: list[str] = Field(
        default_factory=lambda: ["read", "simulate"],
        description="Granted permission scopes.",
    )
    rate_limit_rpm: int = Field(
        default=60,
        ge=1,
        description="Rate limit in requests per minute.",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    active: bool = True
