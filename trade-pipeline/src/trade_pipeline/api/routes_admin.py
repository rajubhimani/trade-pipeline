"""Admin endpoints — feature flag management.

Protected by the same JWT auth as /trades — there's no separate admin-role
system here (out of scope, see docs/features/feature-flags.md); a real
deployment would add role-based access control on top of this. The point
of this feature is the flag mechanism itself: the `feature_flags` table is
the actual source of truth, so an operator could equally well flip a flag
with a direct `UPDATE feature_flags SET enabled = true WHERE name = ...` —
this endpoint is a convenience, not the only way to change it.
"""

from fastapi import APIRouter

from trade_pipeline.api.dependencies import CurrentUserDep, SessionDep
from trade_pipeline.api.schemas import FeatureFlagOut, FeatureFlagUpdate
from trade_pipeline.common.feature_flags import is_enabled, set_enabled

router = APIRouter(prefix="/admin/feature-flags", tags=["admin"])


@router.get("/{name}", response_model=FeatureFlagOut)
async def get_flag(name: str, session: SessionDep, current_user: CurrentUserDep) -> FeatureFlagOut:
    enabled = await is_enabled(session, name)
    return FeatureFlagOut(name=name, enabled=enabled)


@router.patch("/{name}", response_model=FeatureFlagOut)
async def update_flag(
    name: str, body: FeatureFlagUpdate, session: SessionDep, current_user: CurrentUserDep
) -> FeatureFlagOut:
    row = await set_enabled(session, name, body.enabled)
    return FeatureFlagOut(name=row.name, enabled=row.enabled)
