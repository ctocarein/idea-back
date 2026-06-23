"""Configuration partagée des tests.

Pose des variables d'environnement minimales pour que `get_settings()` se construise
sans .env réel. Les tests unitaires du socle ne touchent ni la DB ni Redis.
"""

from __future__ import annotations

import os

# Doit être posé AVANT tout import qui appellerait get_settings().
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-long-enough-ok")
os.environ.setdefault("APP_ENV", "local")
