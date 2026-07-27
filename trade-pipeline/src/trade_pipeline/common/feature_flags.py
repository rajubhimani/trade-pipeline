"""Feature flags — stored in Postgres, toggled via a DB update or the
/admin/feature-flags API, not env vars/redeploys.

Chosen over env-var/process-restart toggles: a flag needs to flip at
runtime without redeploying or restarting every API worker process. Source
of truth is the `feature_flags` table; each request reads the current value
through the same per-request async DB session already in use (no extra
connection or resource). No caching layer — this project's request volume
doesn't justify the added staleness-window complexity of a cache
invalidation scheme; every lookup is a real (cheap, primary-key) read.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from trade_pipeline.common.db_models import FeatureFlag

# Used only when no row exists yet for a given flag name — a flag with no
# row is "not yet toggled," not an error.
DEFAULT_FLAGS: dict[str, bool] = {
    "enrichment_enabled": False,
}


async def is_enabled(session: AsyncSession, name: str) -> bool:
    row = await session.get(FeatureFlag, name)
    if row is None:
        return DEFAULT_FLAGS.get(name, False)
    return row.enabled


async def set_enabled(session: AsyncSession, name: str, enabled: bool) -> FeatureFlag:
    row = await session.get(FeatureFlag, name)
    if row is None:
        row = FeatureFlag(name=name, enabled=enabled)
        session.add(row)
    else:
        row.enabled = enabled
    await session.commit()
    await session.refresh(row)
    return row
