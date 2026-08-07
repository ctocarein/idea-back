"""Garanties de stockage des liens de partage."""

from __future__ import annotations

from app.sharing.models import ProjectShare


def test_project_share_never_persists_raw_token() -> None:
    columns = set(ProjectShare.__table__.columns.keys())
    assert "token_hash" in columns
    assert "token" not in columns
