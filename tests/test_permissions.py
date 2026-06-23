"""Tests de la matrice de permissions — priorité de test (cas d'autorisation)."""

from __future__ import annotations

from uuid import uuid4

from app.iam.models import AccountStatus, Role, User
from app.iam.permissions import ROLE_PERMISSIONS, Permission, permissions_for


def _user(role: Role) -> User:
    return User(
        id=uuid4(),
        email=f"{role.value}@test",
        password_hash="x",
        full_name="Test",
        role=role,
        status=AccountStatus.ACTIVE,
    )


def test_founder_has_diagnostic_but_not_admin_powers() -> None:
    perms = permissions_for(_user(Role.FOUNDER), set())
    assert Permission.DIAGNOSTIC_RUN in perms
    assert Permission.PITCHSIM_RUN in perms
    assert Permission.USER_MANAGE not in perms


def test_mentor_cannot_sign_without_explicit_grant() -> None:
    # Le mentor de base (coach) n'a PAS le pouvoir de certifier.
    base = permissions_for(_user(Role.MENTOR), set())
    assert Permission.CERTIFICATION_SIGN not in base

    # On le promeut mentor-certificateur via un grant explicite, sans changer le rôle.
    promoted = permissions_for(_user(Role.MENTOR), {Permission.CERTIFICATION_SIGN})
    assert Permission.CERTIFICATION_SIGN in promoted


def test_admin_has_governance_permissions() -> None:
    perms = permissions_for(_user(Role.ADMIN), set())
    assert {
        Permission.USER_MANAGE,
        Permission.INVITATION_SEND,
        Permission.PERMISSION_GRANT,
        Permission.AUDIT_READ,
    } <= perms


def test_grants_union_with_role_defaults() -> None:
    perms = permissions_for(_user(Role.FOUNDER), {Permission.AUDIT_READ})
    assert ROLE_PERMISSIONS[Role.FOUNDER] <= perms
    assert Permission.AUDIT_READ in perms
