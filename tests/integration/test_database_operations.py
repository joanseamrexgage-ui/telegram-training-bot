#!/usr/bin/env python3
"""
TASK 1.5: Database Operation Testing
Comprehensive integration tests for database/crud.py

Categories:
- user CRUD operations
- transaction safety (commit/rollback)
- connection pool exhaustion
- activity logging integration
- redis+db consistency
- constraint validations (unique/foreign keys)
- N+1 query prevention
"""
import asyncio
import os
import time
import random
import pytest

from typing import List

try:
    from database import crud
    from database.models import User, UserActivity
except Exception:
    pytest.skip("Database modules not available", allow_module_level=True)

pytestmark = pytest.mark.asyncio


class TestDatabaseOperations:
    async def test_create_read_update_delete_user(self, db_session):
        # create
        user = await crud.create_user(db_session, telegram_id=987654, full_name="Test User")
        assert user.id is not None
        assert user.telegram_id == 987654
        # read
        fetched = await crud.get_user_by_telegram_id(db_session, 987654)
        assert fetched and fetched.id == user.id
        # update
        updated = await crud.update_user(db_session, user.id, full_name="Updated User")
        assert updated.full_name == "Updated User"
        # delete
        await crud.delete_user(db_session, user.id)
        assert await crud.get_user_by_telegram_id(db_session, 987654) is None

    async def test_get_or_create_user_idempotent(self, db_session):
        u1 = await crud.get_or_create_user(db_session, telegram_id=1111, full_name="Alpha")
        u2 = await crud.get_or_create_user(db_session, telegram_id=1111, full_name="Beta")
        assert u1.id == u2.id
        assert (await crud.get_user_by_telegram_id(db_session, 1111)).full_name in {"Alpha","Beta"}

    async def test_transaction_commit_and_rollback(self, db_session):
        # commit path
        async with db_session.begin():
            u = await crud.create_user(db_session, telegram_id=2222, full_name="Tx User")
            assert u.id is not None
        assert await crud.get_user_by_telegram_id(db_session, 2222) is not None
        # rollback path
        try:
            async with db_session.begin():
                await crud.create_user(db_session, telegram_id=3333, full_name="Rollback User")
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass
        assert await crud.get_user_by_telegram_id(db_session, 3333) is None

    async def test_connection_pool_exhaustion(self, async_engine):
        # Create many concurrent short transactions to pressure the pool
        from sqlalchemy.ext.asyncio import async_sessionmaker
        Session = async_sessionmaker(async_engine, expire_on_commit=False)
        async def short_tx(i):
            async with Session() as s:
                # simple lightweight query
                await s.execute(crud.sa_text("SELECT 1"))
        tasks = [asyncio.create_task(short_tx(i)) for i in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(failures) <= 5  # allow few timeouts under pressure

    async def test_activity_logging_integration(self, db_session):
        user = await crud.get_or_create_user(db_session, telegram_id=4444, full_name="Act User")
        await crud.log_user_activity(db_session, user_id=user.id, action="visit", section="menu", details="general")
        activities: List[UserActivity] = await crud.get_user_activity(db_session, user.id, limit=10)
        assert any(a.action == "visit" and a.section == "menu" for a in activities)

    async def test_redis_database_consistency(self, db_session, redis_client):
        # emulate FSM start -> db user read -> data store
        uid = random.randint(100000, 999999)
        await crud.get_or_create_user(db_session, telegram_id=uid, full_name="FSM User")
        key = f"fsm:{uid}:{uid}"
        await redis_client.hset(key, mapping={"state": "MenuStates:main_menu", "data": "{}"})
        # check both exist
        db_user = await crud.get_user_by_telegram_id(db_session, uid)
        state = await redis_client.hget(key, "state")
        assert db_user is not None and state == "MenuStates:main_menu"

    async def test_unique_constraint_violation(self, db_session):
        await crud.get_or_create_user(db_session, telegram_id=5555, full_name="Unique")
        # second insert with same telegram_id should not create new row
        u2 = await crud.get_or_create_user(db_session, telegram_id=5555, full_name="Unique2")
        users = await crud.get_all_users(db_session, limit=100)
        assert sum(1 for u in users if u.telegram_id == 5555) == 1
        assert u2 is not None

    async def test_foreign_key_constraint(self, db_session):
        # create activity with wrong user id should fail
        with pytest.raises(Exception):
            await crud.log_user_activity(db_session, user_id=9999999, action="x", section="y", details="z")

    async def test_n_plus_one_prevention_on_stats(self, db_session):
        # create several users and activities
        for i in range(10):
            u = await crud.get_or_create_user(db_session, telegram_id=8000+i, full_name=f"U{i}")
            await crud.log_user_activity(db_session, user_id=u.id, action="visit", section="menu", details=str(i))
        # wrapped function should eager load to keep queries small
        from contextlib import asynccontextmanager
        query_count = 0
        original_execute = db_session.execute
        async def counting_execute(*args, **kwargs):
            nonlocal query_count
            query_count += 1
            return await original_execute(*args, **kwargs)
        db_session.execute = counting_execute  # type: ignore
        _stats = await crud.get_user_statistics(db_session)
        assert query_count <= 3

