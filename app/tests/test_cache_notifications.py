# File: app/tests/test_cache_notifications.py
"""Cache manager (on fakeredis), WebSocket connection manager and SSE manager."""

import json
from unittest.mock import AsyncMock

from app.common.cache_utils import CacheManager, SessionCache, cache_manager, cached
from app.services.notification_service import ConnectionManager, SSEManager


class TestCacheManager:
    async def test_scalar_roundtrip_and_ttl(self, mock_redis):
        cache = CacheManager(mock_redis)
        assert await cache.set("k", {"a": 1}, ttl=60)
        assert await cache.get("k") == {"a": 1}
        assert await cache.exists("k")
        assert 0 < await cache.ttl("k") <= 60
        assert await cache.expire("k", 5)
        assert await cache.delete("k") and not await cache.exists("k")
        assert await cache.get("missing", default="d") == "d"

    async def test_increment_and_collections(self, mock_redis):
        cache = CacheManager(mock_redis)
        assert await cache.increment("n") == 1 and await cache.increment("n", 4) == 5

        await cache.set_hash("h", {"x": [1, 2], "y": "s"}, ttl=30)
        assert await cache.get_hash("h") == {"x": [1, 2], "y": "s"}
        assert await cache.get_hash("h", fields=["y"]) == {"y": "s"}

        await cache.add_to_set("s", 1, 2, ttl=30)
        assert sorted(await cache.get_set("s")) == [1, 2]
        assert await cache.remove_from_set("s", 1) == 1

        await cache.push_to_list("l", "a", "b")
        assert await cache.get_list("l") == ["b", "a"]
        assert await cache.pop_from_list("l") == ["a"]

        await cache.set("pat:1", 1)
        await cache.set("pat:2", 2)
        assert await cache.clear_pattern("pat:*") == 2

    async def test_unparseable_value_returns_default(self, mock_redis):
        await mock_redis.set("raw", "not json")
        assert await CacheManager(mock_redis).get("raw", default=None) is None

    async def test_cached_decorator_memoises(self, mock_redis):
        calls = 0

        @cached(ttl=60, key_prefix="sq")
        async def square(n: int) -> int:
            nonlocal calls
            calls += 1
            return n * n

        assert await square(4) == 16 and await square(4) == 16
        assert calls == 1
        assert await mock_redis.exists("sq:4")

    async def test_session_cache(self, mock_redis):
        sessions = SessionCache(cache_manager)
        assert await sessions.create_session("sid", 7, {"ua": "x"})
        stored = await sessions.get_session("sid")
        assert stored["user_id"] == 7 and stored["ua"] == "x"
        assert await sessions.update_session("sid", {"ua": "y"})
        assert (await sessions.get_session("sid"))["ua"] == "y"
        assert await sessions.extend_session("sid", 10)
        assert await sessions.delete_session("sid")
        assert not await sessions.update_session("sid", {})


class _FakeSocket:
    def __init__(self, fail: bool = False):
        self.sent: list[str] = []
        self.fail = fail

    async def send_text(self, text: str) -> None:
        if self.fail:
            raise RuntimeError("closed")
        self.sent.append(text)


class TestConnectionManager:
    async def test_routing(self):
        manager = ConnectionManager()
        a, b, anon = _FakeSocket(), _FakeSocket(), _FakeSocket()
        await manager.connect(a, "a", user_id=1)
        await manager.connect(b, "b", user_id=1)
        await manager.connect(anon, "anon")

        assert await manager.send_to_user(1, {"m": 1}) is True
        assert len(a.sent) == len(b.sent) == 1 and anon.sent == []
        assert await manager.send_to_user(42, {"m": 1}) is False

        await manager.subscribe_to_channel("a", "news")
        await manager.subscribe_to_channel("anon", "news")
        await manager.broadcast_to_channel("news", {"n": 1})
        assert json.loads(anon.sent[-1]) == {"n": 1}
        await manager.unsubscribe_from_channel("anon", "news")

        await manager.join_room("b", "r1")
        await manager.broadcast_to_room("r1", {"r": 1})
        assert json.loads(b.sent[-1]) == {"r": 1}
        await manager.leave_room("b", "r1")

        stats = manager.get_stats()
        assert stats["total_connections"] == 3 and stats["authenticated_connections"] == 2
        assert stats["channels"]["news"] == 1

    async def test_failed_send_disconnects(self):
        manager = ConnectionManager()
        await manager.connect(_FakeSocket(fail=True), "bad", user_id=9)
        assert await manager.send_personal_message("x", "bad") is False
        assert "bad" not in manager.active_connections
        assert await manager.send_personal_message("x", "unknown") is False
        manager.disconnect("unknown")  # idempotent


class TestSSEManager:
    async def test_channels_users_and_cleanup(self):
        sse = SSEManager()
        await sse.subscribe_to_channel("c1", "news", user_id=1)
        await sse.subscribe_to_user_events("c1", 1)
        await sse.subscribe_to_channel("c2", "news")

        assert await sse.publish_to_channel("news", {"id": "m1"}) == 2
        assert await sse.publish_to_channel("empty", {"id": "m2"}) == 0
        assert await sse.send_to_user(1, {"id": "m3"}) is True
        assert await sse.send_to_user(2, {"id": "m3"}) is False

        assert [m["id"] for m in await sse.get_messages_for_client("c1")] == ["m1", "m3"]
        assert await sse.get_messages_for_client("c1") == []

        stats = await sse.get_stats()
        assert stats["total_clients"] == 2 and stats["authenticated_clients"] == 1
        assert stats["total_messages_sent"] == 3 and stats["uptime_seconds"] >= 0
        channels = {c["name"]: c["subscriber_count"] for c in await sse.get_active_channels()}
        assert channels["news"] == 2 and channels["user_1"] == 1

        assert await sse.clear_channel("news") == 1  # c2 still had m1 queued
        await sse.remove_client("c1")
        await sse.remove_client("c1")  # idempotent
        assert (await sse.get_stats())["total_clients"] == 1


async def test_sse_http_publish_paths(async_client, auth_headers):
    manager = SSEManager()
    await manager.subscribe_to_channel("cli", "general", user_id=1)
    from app.api.v1 import sse as sse_module

    original = sse_module.sse_manager
    sse_module.sse_manager = manager
    try:
        stats = await async_client.get("/api/v1/sse/stats")
        assert stats.json()["total_clients"] == 1
        channels = await async_client.get("/api/v1/sse/channels")
        assert channels.json()["channels"][0]["name"] == "general"
        broadcast = await async_client.post(
            "/api/v1/sse/broadcast", json={"content": "hi"}, params={"channels": "general,other"}
        )
        assert broadcast.json()["total_recipients"] == 1
        cleared = await async_client.delete("/api/v1/sse/channels/general")
        assert cleared.json()["messages_cleared"] == 1
        test_events = await async_client.post(
            "/api/v1/sse/test/events", params={"channel": "general", "count": 2, "interval": 0.1}
        )
        assert len(test_events.json()["event_ids"]) == 2
    finally:
        sse_module.sse_manager = original


async def test_websocket_stats_endpoints(async_client):
    from app.api.v1 import websocket as ws_module

    manager = ConnectionManager()
    await manager.connect(AsyncMock(), "x", user_id=3)
    await manager.subscribe_to_channel("x", "chat")
    await manager.join_room("x", "room")
    original = ws_module.connection_manager
    ws_module.connection_manager = manager
    try:
        assert (await async_client.get("/api/v1/ws/stats")).json()["total_connections"] == 1
        assert (await async_client.get("/api/v1/ws/channels")).json()["channels"] == ["chat"]
        assert (await async_client.get("/api/v1/ws/rooms")).json()["rooms"] == ["room"]
    finally:
        ws_module.connection_manager = original
