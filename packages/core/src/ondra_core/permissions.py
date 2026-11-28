"""Role-based access control (BUILD_PLAN.md §2).

Permissions are checked server-side on every request. Row visibility rules that depend on the record
(VIP contacts) live next to the queries that need them; see `can_see_vips`.
"""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"  # the top role: everything (owner merged into it, 2026-11-28)
    MANAGER = "manager"
    SALES = "sales"
    SERVICE = "service"
    OPS = "ops"
    VIEWER = "viewer"


class Perm(StrEnum):
    CONTACTS_READ = "contacts:read"
    CONTACTS_WRITE = "contacts:write"
    VEHICLES_READ = "vehicles:read"
    VEHICLES_WRITE = "vehicles:write"
    CONVERSATIONS_READ = "conversations:read"
    CONVERSATIONS_REPLY = "conversations:reply"
    DEALS_READ = "deals:read"
    DEALS_WRITE = "deals:write"
    TASKS_READ = "tasks:read"
    TASKS_WRITE = "tasks:write"
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"
    SETTINGS_MANAGE = "settings:manage"
    KNOWLEDGE_WRITE = "knowledge:write"  # answer what Ondra didn't know; managers can, they know the answers
    INTEGRATIONS_MANAGE = "integrations:manage"
    AUDIT_READ = "audit:read"


_READ_WORK = {Perm.CONTACTS_READ, Perm.VEHICLES_READ, Perm.CONVERSATIONS_READ, Perm.DEALS_READ, Perm.TASKS_READ}
_DO_WORK = _READ_WORK | {Perm.CONTACTS_WRITE, Perm.CONVERSATIONS_REPLY, Perm.DEALS_WRITE, Perm.TASKS_WRITE}

ROLE_PERMISSIONS: dict[Role, frozenset[Perm]] = {
    Role.ADMIN: frozenset(Perm),
    Role.MANAGER: frozenset(_DO_WORK | {Perm.VEHICLES_WRITE, Perm.USERS_READ, Perm.AUDIT_READ, Perm.KNOWLEDGE_WRITE}),
    Role.SALES: frozenset(_DO_WORK),
    Role.SERVICE: frozenset(_DO_WORK),
    Role.OPS: frozenset(_DO_WORK),
    Role.VIEWER: frozenset(_READ_WORK),
}


def has_perm(role: str, perm: Perm) -> bool:
    return perm in ROLE_PERMISSIONS.get(Role(role), frozenset())


def can_see_vips(role: str) -> bool:
    """VIP contacts are visible to admins and managers. Anyone else sees a VIP only if they are its handler."""
    return Role(role) in (Role.ADMIN, Role.MANAGER)
