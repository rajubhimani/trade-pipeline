"""End-to-end workflow tests against Temporal's time-skipping test server —
same approach as tests/enrichment/test_temporal_workflow.py (session-scoped
environment, fresh Worker + unique task queue per test).
"""

import uuid

import pytest
import pytest_asyncio
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from trade_pipeline.api.auth.refresh_tokens import RefreshTokenStore
from trade_pipeline.api.auth.refresh_workflow import (
    RefreshTokenActivities,
    RefreshTokenRotationWorkflow,
)


@pytest_asyncio.fixture(scope="session")
async def env():
    async with await WorkflowEnvironment.start_time_skipping() as environment:
        yield environment


async def _run_workflow(env: WorkflowEnvironment, store: RefreshTokenStore, token: str):
    activities = RefreshTokenActivities(store)
    task_queue = f"refresh-{uuid.uuid4()}"
    async with Worker(
        env.client,
        task_queue=task_queue,
        workflows=[RefreshTokenRotationWorkflow],
        activities=[activities.rotate],
    ):
        return await env.client.execute_workflow(
            RefreshTokenRotationWorkflow.run,
            token,
            id=f"wf-{uuid.uuid4()}",
            task_queue=task_queue,
        )


async def test_workflow_rotates_a_valid_token(env, redis_client):
    store = RefreshTokenStore(redis=redis_client)
    token = store.issue("user-42")

    result = await _run_workflow(env, store, token)

    assert result.user_id == "user-42"
    assert result.new_token != token
    # Rotation is single-use — the old token no longer works.
    assert redis_client.get(f"refresh:{token}") is None


async def test_workflow_fails_without_retrying_on_reused_token(env, redis_client):
    store = RefreshTokenStore(redis=redis_client)

    with pytest.raises(WorkflowFailureError):
        await _run_workflow(env, store, "never-issued")
