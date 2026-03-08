"""Tests for multi-tenant architecture."""

import pytest
from trust_kernel.multitenancy import (
    TenantManager, RBACManager, Role, Tenant, APIToken, UserBinding,
)


class TestTenantManager:
    def test_create_tenant(self):
        tm = TenantManager()
        tenant, api_key = tm.create_tenant(name="Acme Corp", tier="pro")
        assert tenant.name == "Acme Corp"
        assert tenant.tier == "pro"
        assert tenant.active
        assert api_key.startswith("pf_")

    def test_authenticate_by_key(self):
        tm = TenantManager()
        tenant, api_key = tm.create_tenant(name="TestOrg")
        found = tm.authenticate_by_key(api_key)
        assert found is not None
        assert found.tenant_id == tenant.tenant_id

    def test_authenticate_invalid_key(self):
        tm = TenantManager()
        tm.create_tenant(name="TestOrg")
        assert tm.authenticate_by_key("invalid-key") is None

    def test_create_and_authenticate_token(self):
        tm = TenantManager()
        tenant, _ = tm.create_tenant(name="TokenOrg")
        token, raw = tm.create_token(tenant.tenant_id, name="my-token", scopes=["read", "execute"])
        assert raw.startswith("pft_")

        result = tm.authenticate_token(raw)
        assert result is not None
        found_tenant, found_token = result
        assert found_tenant.tenant_id == tenant.tenant_id
        assert found_token.name == "my-token"

    def test_revoke_token(self):
        tm = TenantManager()
        tenant, _ = tm.create_tenant(name="RevokeOrg")
        token, raw = tm.create_token(tenant.tenant_id)
        tm.revoke_token(token.token_id)
        assert tm.authenticate_token(raw) is None

    def test_deactivate_tenant(self):
        tm = TenantManager()
        tenant, api_key = tm.create_tenant(name="DeactivateOrg")
        tm.deactivate_tenant(tenant.tenant_id)
        assert tm.authenticate_by_key(api_key) is None

    def test_tier_rate_limits(self):
        tm = TenantManager()
        free, _ = tm.create_tenant(name="Free", tier="free")
        pro, _ = tm.create_tenant(name="Pro", tier="pro")
        ent, _ = tm.create_tenant(name="Enterprise", tier="enterprise")
        assert free.rate_limit_rpm < pro.rate_limit_rpm < ent.rate_limit_rpm

    def test_tier_budgets(self):
        tm = TenantManager()
        free, _ = tm.create_tenant(name="Free", tier="free")
        ent, _ = tm.create_tenant(name="Enterprise", tier="enterprise")
        assert free.budget_limit < ent.budget_limit

    def test_list_tenants(self):
        tm = TenantManager()
        tm.create_tenant(name="Org1")
        tm.create_tenant(name="Org2")
        assert len(tm.list_tenants()) == 2

    def test_list_tokens(self):
        tm = TenantManager()
        tenant, _ = tm.create_tenant(name="TokenListOrg")
        tm.create_token(tenant.tenant_id, name="t1")
        tm.create_token(tenant.tenant_id, name="t2")
        tokens = tm.list_tokens(tenant.tenant_id)
        assert len(tokens) == 2

    def test_hierarchy(self):
        tm = TenantManager()
        org, _ = tm.create_tenant(name="ParentOrg")
        team, _ = tm.create_tenant(name="Team A", parent_id=org.tenant_id)
        assert team.parent_id == org.tenant_id
        children = tm.list_tenants(parent_id=org.tenant_id)
        assert len(children) == 1

    def test_scope_check(self):
        tm = TenantManager()
        tenant, _ = tm.create_tenant(name="ScopeOrg")
        token, _ = tm.create_token(tenant.tenant_id, scopes=["read"])
        assert tm.check_scope(token, "read")
        assert not tm.check_scope(token, "admin")

    def test_admin_scope_grants_all(self):
        tm = TenantManager()
        tenant, _ = tm.create_tenant(name="AdminOrg")
        token, _ = tm.create_token(tenant.tenant_id, scopes=["admin"])
        assert tm.check_scope(token, "read")
        assert tm.check_scope(token, "execute")
        assert tm.check_scope(token, "anything")


class TestRBAC:
    def test_bind_and_check(self):
        rbac = RBACManager()
        tm = TenantManager()
        tenant, _ = tm.create_tenant(name="RBAC Org")
        rbac.bind_user("user-1", tenant.tenant_id, role="operator")
        assert rbac.check_access("user-1", tenant.tenant_id, "execute")
        assert not rbac.check_access("user-1", tenant.tenant_id, "manage_tenants")

    def test_admin_has_all_permissions(self):
        rbac = RBACManager()
        rbac.bind_user("admin-1", "t1", role="admin")
        assert rbac.check_access("admin-1", "t1", "execute")
        assert rbac.check_access("admin-1", "t1", "manage_tenants")
        assert rbac.check_access("admin-1", "t1", "export_ledger")

    def test_viewer_limited(self):
        rbac = RBACManager()
        rbac.bind_user("viewer-1", "t1", role="viewer")
        assert rbac.check_access("viewer-1", "t1", "view_dashboard")
        assert not rbac.check_access("viewer-1", "t1", "execute")
        assert not rbac.check_access("viewer-1", "t1", "query_ledger")

    def test_auditor_permissions(self):
        rbac = RBACManager()
        rbac.bind_user("auditor-1", "t1", role="auditor")
        assert rbac.check_access("auditor-1", "t1", "query_ledger")
        assert rbac.check_access("auditor-1", "t1", "export_ledger")
        assert not rbac.check_access("auditor-1", "t1", "execute")

    def test_unknown_user_denied(self):
        rbac = RBACManager()
        assert not rbac.check_access("unknown", "t1", "view_dashboard")

    def test_invalid_role_raises(self):
        rbac = RBACManager()
        with pytest.raises(ValueError, match="Invalid role"):
            rbac.bind_user("user-1", "t1", role="superadmin")

    def test_remove_binding(self):
        rbac = RBACManager()
        rbac.bind_user("user-1", "t1", role="operator")
        assert rbac.check_access("user-1", "t1", "execute")
        rbac.remove_binding("user-1", "t1")
        assert not rbac.check_access("user-1", "t1", "execute")

    def test_list_bindings(self):
        rbac = RBACManager()
        rbac.bind_user("u1", "t1", role="admin")
        rbac.bind_user("u2", "t1", role="viewer")
        bindings = rbac.list_bindings("t1")
        assert len(bindings) == 2


class TestRole:
    def test_all_roles(self):
        roles = Role.all_roles()
        assert "admin" in roles
        assert "operator" in roles
        assert "auditor" in roles
        assert "viewer" in roles

    def test_has_permission(self):
        assert Role.has_permission("admin", "manage_tenants")
        assert not Role.has_permission("viewer", "manage_tenants")
