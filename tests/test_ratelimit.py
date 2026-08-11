"""Rate-limiter — chemin Redis nominal + repli en mémoire quand Redis est KO.

Le repli doit LIMITER (ni fail-open « tout passe », ni fail-closed « tout bloque »).
"""

from __future__ import annotations

import pytest

from app.core import ratelimit
from app.core.ratelimit import RateLimiter


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    async def expire(self, key: str, seconds: int) -> None:
        pass


class BoomRedis:
    async def incr(self, key: str) -> int:
        raise RuntimeError("redis down")

    async def expire(self, key: str, seconds: int) -> None:
        raise RuntimeError("redis down")


@pytest.fixture(autouse=True)
def _clear_memory() -> None:
    ratelimit._MEM_BUCKETS.clear()


class TestRedisPath:
    @pytest.mark.asyncio
    async def test_limite_normalement_via_redis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeRedis()  # une seule instance partagée entre les appels
        monkeypatch.setattr(ratelimit, "get_redis", lambda: fake)
        rl = RateLimiter(scope="t_redis", limit=2, window_seconds=60)
        assert [await rl.allow("ip") for _ in range(3)] == [True, True, False]


class TestInMemoryFallback:
    @pytest.mark.asyncio
    async def test_repli_limite_quand_redis_ko(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ratelimit, "get_redis", lambda: BoomRedis())
        rl = RateLimiter(scope="t_boom", limit=3, window_seconds=60)
        results = [await rl.allow("ipx") for _ in range(4)]
        # Ni fail-open ([T,T,T,T]) ni fail-closed ([F,F,F,F]) : on limite bien.
        assert results == [True, True, True, False]

    @pytest.mark.asyncio
    async def test_repli_si_get_redis_leve(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom() -> object:
            raise RuntimeError("no redis")

        monkeypatch.setattr(ratelimit, "get_redis", boom)
        rl = RateLimiter(scope="t_getboom", limit=1, window_seconds=60)
        assert [await rl.allow("ip") for _ in range(2)] == [True, False]

    @pytest.mark.asyncio
    async def test_buckets_independants_par_identifiant(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ratelimit, "get_redis", lambda: BoomRedis())
        rl = RateLimiter(scope="t_indep", limit=1, window_seconds=60)
        assert await rl.allow("a") is True
        assert await rl.allow("a") is False
        assert await rl.allow("b") is True  # une autre IP a son propre compteur
