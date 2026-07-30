"""Deterministic Temporal workflow IDs for the per-trade enrichment path.

Deterministic (not a random UUID) on purpose: the same trade must always
resolve to the same workflow ID, so re-dispatching an outbox row that was
already started (e.g. after a worker crash between "start_workflow" and
"mark dispatched") lands on ``WorkflowAlreadyStartedError`` instead of
spawning a second workflow for the same trade — see outbox.py.
"""

import hashlib
from datetime import datetime


def compute_workflow_id(broker_id: str, trade_id: str, timestamp: datetime) -> str:
    digest = hashlib.sha256(f"{broker_id}:{trade_id}:{timestamp.isoformat()}".encode()).hexdigest()
    return f"enrichment-{digest}"
