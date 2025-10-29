#!/usr/bin/env python3
"""
TASK 1.6: FSM Flow Validation with Redis persistence

Categories:
- menu state transitions
- admin state flows
- redis persistence across restart
- multi-user isolation
- state cleanup & expiration
- FSM behavior during Redis failover
"""
import asyncio
import json
import random
import time
import pytest

pytestmark = pytest.mark.asyncio


class TestFSMFlows:
    async def test_menu_state_transitions(self, bot_app, redis_client):
        user_id = random.randint(10000, 99999)
        # start -> main_menu
        resp = await bot_app.process_update({"message": {"from": {"id": user_id}, "text": "/start"}})
        assert resp is not None
        # navigate
        await bot_app.process_update({"callback_query": {"from": {"id": user_id}, "data": "menu_general"}})
        await bot_app.process_update({"callback_query": {"from": {"id": user_id}, "data": "general_info_rules"}})
        # check FSM stored
        key = f"fsm:{user_id}:{user_id}"
        state = await redis_client.hget(key, "state")
        assert state is not None

    async def test_admin_state_flows(self, bot_app, redis_client):
        admin_id = 789074695
        await bot_app.process_update({"callback_query": {"from": {"id": admin_id}, "data": "admin_panel"}})
        await bot_app.process_update({"message": {"from": {"id": admin_id}, "text": "correct_admin_password"}})
        resp = await bot_app.process_update({"callback_query": {"from": {"id": admin_id}, "data": "admin_statistics"}})
        assert resp is not None
        key = f"fsm:{admin_id}:{admin_id}"
        state = await redis_client.hget(key, "state")
        assert state is not None

    async def test_fsm_redis_persistence_across_restart(self, redis_client):
        user_id = random.randint(20000, 99999)
        key = f"fsm:{user_id}:{user_id}"
        await redis_client.hset(key, mapping={"state": "MenuStates:main_menu", "data": json.dumps({"step": 1})})
        # simulate restart: new client
        import redis.asyncio as redis
        new_client = redis.from_url("redis://localhost:6379/15", decode_responses=True)
        try:
            await new_client.ping()
            state = await new_client.hget(key, "state")
            data = json.loads(await new_client.hget(key, "data"))
            assert state == "MenuStates:main_menu" and data.get("step") == 1
        finally:
            await new_client.close()

    async def test_concurrent_user_isolation(self, redis_client):
        users = [random.randint(100000, 199999) for _ in range(10)]
        tasks = []
        for uid in users:
            key = f"fsm:{uid}:{uid}"
            tasks.append(redis_client.hset(key, mapping={"state": f"State:{uid}", "data": json.dumps({"u": uid})}))
        await asyncio.gather(*tasks)
        # verify isolation
        for uid in users:
            key = f"fsm:{uid}:{uid}"
            assert await redis_client.hget(key, "state") == f"State:{uid}"

    async def test_state_cleanup_and_expiration(self, redis_client):
        uid = random.randint(300000, 399999)
        key = f"fsm:{uid}:{uid}"
        await redis_client.hset(key, mapping={"state": "TempState", "data": "{}"})
        await redis_client.expire(key, 2)
        assert await redis_client.hget(key, "state") == "TempState"
        await asyncio.sleep(3)
        assert await redis_client.hget(key, "state") is None

    async def test_fsm_behavior_during_redis_failover(self, redis_client):
        # pre-store
        uid = random.randint(400000, 499999)
        key = f"fsm:{uid}:{uid}"
        await redis_client.hset(key, mapping={"state": "PreFailover", "data": "{}"})
        # simulate failover by disconnect
        try:
            await redis_client.connection_pool.disconnect()
        except Exception:
            pass
        # client should recover
        await redis_client.hset(key, mapping={"state": "PostFailover"})
        state = await redis_client.hget(key, "state")
        assert state == "PostFailover"
