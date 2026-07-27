"""Activity-level tests — no Temporal runtime needed (see
tests/enrichment/test_temporal_activities.py for why: @activity.defn only
changes registration, the method is still directly awaitable).
"""

import pytest
from temporalio.exceptions import ApplicationError

from trade_pipeline.api.auth.refresh_tokens import RefreshTokenStore
from trade_pipeline.api.auth.refresh_workflow import RefreshTokenActivities


async def test_rotate_activity_returns_new_token(redis_client):
    store = RefreshTokenStore(redis=redis_client)
    token = store.issue("user-1")
    activities = RefreshTokenActivities(store)

    result = await activities.rotate(token)

    assert result.user_id == "user-1"
    assert result.new_token != token


async def test_rotate_activity_raises_non_retryable_for_unknown_token(redis_client):
    store = RefreshTokenStore(redis=redis_client)
    activities = RefreshTokenActivities(store)

    with pytest.raises(ApplicationError) as exc_info:
        await activities.rotate("does-not-exist")

    assert exc_info.value.non_retryable is True
