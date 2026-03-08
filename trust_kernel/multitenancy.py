"""
Preflight Multi-Tenant Architecture.

Provides organization, team, and project isolation with separate
ledgers, policy engines, budgets, and API tokens per tenant.
No global shared state leakage permitted.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class Tenant:
    """Represents an organization or team."""
    tenant_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    tier: str = "free"  # free, pro, enterprise
    parent_id: Optional[str] = None  # For team -> org hierarchy
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    settings: dict[str, Any] = field(default_factory=dict)
    active: bool = True
    api_key_hash: str = ""
    rate_limit_rpm: int = 1000  # Requests per minute
    budget_limit: float = 10000.0
    max_agents: int = 100


@dataclass
class APIToken:
    """Scoped API token for a tenant."""
    token_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    token_hash: str = ""
    name: str = ""
    scopes: list[str] = field(default_factory=lambda: ["read", "execute"])
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    expires_at: Optional[datetime] = None
    revoked: bool = False
    last_used: Optional[datetime] = None


class TenantManager:
    """Manages tenant lifecycle, isolation, and API token scoping.

    Every tenant gets:
    - Isolated ledger namespace
    - Separate policy engine configuration
    - Dedicated budget tracking
    - Scoped API tokens with rate limits
    """

    def __init__(self):
        self._tenants: dict[str, Tenant] = {}
        self._tokens: dict[str, APIToken] = {}
        self._token_to_tenant: dict[str, str] = {}

    def create_tenant(
        self,
        name: str,
        tier: str = "free",
        parent_id: Optional[str] = None,
        settings: Optional[dict] = None,
    ) -> tuple[Tenant, str]:
        """Create a new tenant. Returns (tenant, api_key)."""
        tenant = Tenant(
            name=name,
            tier=tier,
            parent_id=parent_id,
            settings=settings or {},
            rate_limit_rpm=self._tier_rate_limit(tier),
            budget_limit=self._tier_budget_limit(tier),
        )

        # Generate API key
        raw_key = f"pf_{secrets.token_urlsafe(32)}"
        tenant.api_key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        self._tenants[tenant.tenant_id] = tenant
        return tenant, raw_key

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get(tenant_id)

    def authenticate_by_key(self, api_key: str) -> Optional[Tenant]:
        """Authenticate a tenant by API key."""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        for tenant in self._tenants.values():
            if tenant.active and tenant.api_key_hash == key_hash:
                return tenant
        return None

    def create_token(
        self,
        tenant_id: str,
        name: str = "",
        scopes: Optional[list[str]] = None,
    ) -> tuple[APIToken, str]:
        """Create a scoped API token. Returns (token_record, raw_token)."""
        raw_token = f"pft_{secrets.token_urlsafe(32)}"
        token = APIToken(
            tenant_id=tenant_id,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            name=name or f"token-{len(self._tokens)}",
            scopes=scopes or ["read", "execute"],
        )
        self._tokens[token.token_id] = token
        self._token_to_tenant[token.token_hash] = tenant_id
        return token, raw_token

    def authenticate_token(self, raw_token: str) -> Optional[tuple[Tenant, APIToken]]:
        """Authenticate by scoped token. Returns (tenant, token) or None."""
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        tenant_id = self._token_to_tenant.get(token_hash)
        if not tenant_id:
            return None

        tenant = self._tenants.get(tenant_id)
        if not tenant or not tenant.active:
            return None

        for token in self._tokens.values():
            if token.token_hash == token_hash and not token.revoked:
                now = datetime.now(timezone.utc)
                if token.expires_at and now > token.expires_at:
                    return None
                token.last_used = now
                return tenant, token

        return None

    def check_scope(self, token: APIToken, required_scope: str) -> bool:
        """Check if a token has the required scope."""
        if "admin" in token.scopes:
            return True
        return required_scope in token.scopes

    def revoke_token(self, token_id: str) -> bool:
        token = self._tokens.get(token_id)
        if token:
            token.revoked = True
            return True
        return False

    def deactivate_tenant(self, tenant_id: str) -> bool:
        tenant = self._tenants.get(tenant_id)
        if tenant:
            tenant.active = False
            return True
        return False

    def list_tenants(self, parent_id: Optional[str] = None) -> list[Tenant]:
        tenants = list(self._tenants.values())
        if parent_id is not None:
            tenants = [t for t in tenants if t.parent_id == parent_id]
        return tenants

    def list_tokens(self, tenant_id: str) -> list[APIToken]:
        return [t for t in self._tokens.values() if t.tenant_id == tenant_id]

    @staticmethod
    def _tier_rate_limit(tier: str) -> int:
        return {"free": 100, "pro": 1000, "enterprise": 10000}.get(tier, 100)

    @staticmethod
    def _tier_budget_limit(tier: str) -> float:
        return {"free": 100.0, "pro": 10000.0, "enterprise": 1000000.0}.get(
            tier, 100.0
        )


# -- RBAC ------------------------------------------------------------------

class Role:
    """Access control role with granular permissions."""
    ADMIN = "admin"
    OPERATOR = "operator"
    AUDITOR = "auditor"
    VIEWER = "viewer"

    PERMISSIONS = {
        "admin": {
            "execute", "approve", "reject", "query_ledger", "export_ledger",
            "manage_policies", "manage_keys", "manage_tenants", "manage_tokens",
            "view_dashboard", "view_stats", "verify_ledger", "manage_budgets",
        },
        "operator": {
            "execute", "approve", "reject", "query_ledger", "view_dashboard",
            "view_stats", "verify_ledger",
        },
        "auditor": {
            "query_ledger", "export_ledger", "view_dashboard", "view_stats",
            "verify_ledger",
        },
        "viewer": {
            "view_dashboard", "view_stats",
        },
    }

    @classmethod
    def has_permission(cls, role: str, permission: str) -> bool:
        perms = cls.PERMISSIONS.get(role, set())
        return permission in perms

    @classmethod
    def all_roles(cls) -> list[str]:
        return [cls.ADMIN, cls.OPERATOR, cls.AUDITOR, cls.VIEWER]


@dataclass
class UserBinding:
    """Binds a user to a tenant with a specific role."""
    binding_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    tenant_id: str = ""
    role: str = "viewer"
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RBACManager:
    """Role-Based Access Control for multi-tenant deployments."""

    def __init__(self):
        self._bindings: dict[str, list[UserBinding]] = {}  # tenant -> bindings

    def bind_user(
        self, user_id: str, tenant_id: str, role: str = "viewer"
    ) -> UserBinding:
        if role not in Role.all_roles():
            raise ValueError(f"Invalid role: {role}")

        binding = UserBinding(
            user_id=user_id, tenant_id=tenant_id, role=role
        )
        self._bindings.setdefault(tenant_id, []).append(binding)
        return binding

    def get_user_role(self, user_id: str, tenant_id: str) -> Optional[str]:
        for b in self._bindings.get(tenant_id, []):
            if b.user_id == user_id:
                return b.role
        return None

    def check_access(
        self, user_id: str, tenant_id: str, permission: str
    ) -> bool:
        role = self.get_user_role(user_id, tenant_id)
        if not role:
            return False
        return Role.has_permission(role, permission)

    def list_bindings(self, tenant_id: str) -> list[UserBinding]:
        return self._bindings.get(tenant_id, [])

    def remove_binding(self, user_id: str, tenant_id: str) -> bool:
        bindings = self._bindings.get(tenant_id, [])
        for i, b in enumerate(bindings):
            if b.user_id == user_id:
                bindings.pop(i)
                return True
        return False
