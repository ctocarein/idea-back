"""Tests de la garde d'affinage analyste — admin / assigné / rejet (cas 403)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.errors import ForbiddenError
from app.iam.dependencies import AuthContext, guard_assigned_or_admin
from app.iam.models import AccountStatus, Role, User
from app.iam.permissions import Permission


def _ctx(role: Role, perms: set[Permission]) -> AuthContext:
    user = User(
        id=uuid4(),
        email=f"{role.value}@test",
        password_hash="x",
        full_name="Test",
        role=role,
        status=AccountStatus.ACTIVE,
    )
    return AuthContext(user=user, permissions=perms)


def test_admin_can_edit_any_project() -> None:
    ctx = _ctx(Role.ADMIN, {Permission.PROJECT_READ_ANY})
    guard_assigned_or_admin(assignee_id=uuid4(), ctx=ctx)  # ne lève pas, même non assigné


def test_mentor_can_edit_assigned_project() -> None:
    ctx = _ctx(Role.MENTOR, {Permission.MENTOR_REVIEW})
    guard_assigned_or_admin(assignee_id=ctx.user.id, ctx=ctx)  # assigné → ok


def test_mentor_cannot_edit_unassigned_project() -> None:
    ctx = _ctx(Role.MENTOR, {Permission.MENTOR_REVIEW})
    with pytest.raises(ForbiddenError):
        guard_assigned_or_admin(assignee_id=uuid4(), ctx=ctx)


def test_founder_cannot_edit() -> None:
    ctx = _ctx(Role.FOUNDER, {Permission.PROJECT_WRITE_OWN})
    with pytest.raises(ForbiddenError):
        guard_assigned_or_admin(assignee_id=ctx.user.id, ctx=ctx)
