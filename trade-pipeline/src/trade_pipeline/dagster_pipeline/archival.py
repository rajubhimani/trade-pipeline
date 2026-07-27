"""Cold-storage archival — batch pending trades, compress, write to archive/.

Per the plan's Week 6-7 project track: "every 1000 trades, batch them into a
JSON file, compress with compression.zstd (Python 3.14 stdlib), and write to
a local archive/ folder (simulating S3)." Built as a scheduled Dagster asset
rather than living inline in the consumer's per-message loop — see
docs/ARCHITECTURE.md "Where Dagster fits" and docs/features/dagster-archival.md.

The archival logic itself (``archive_pending_trades``) is a plain function
taking a DB session, with no Dagster import at all — the ``@asset`` below is
a thin wrapper, same separation-of-concerns pattern as the Temporal
activities in enrichment/temporal_workflow.py. This means the logic is
directly unit-testable with zero Dagster runtime.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

try:
    from compression import zstd  # 3.14 stdlib
except ImportError:  # pragma: no cover — exercised by the 3.11-3.13 CI matrix legs
    # zstandard (PyPI) has a different API shape (ZstdCompressor/ZstdDecompressor
    # objects, not module-level functions) — wrapped here so the rest of this
    # module can call zstd.compress()/zstd.decompress() either way. This is a
    # real runtime fallback, not just a comment: this project's CI matrix
    # (.github/workflows/ci.yml) actually runs the full test suite on 3.11-3.14,
    # so an import that only works on 3.14 would break three of the four legs.
    import zstandard as _zstandard

    class zstd:  # deliberately mimics the stdlib module's name/API
        @staticmethod
        def compress(data: bytes) -> bytes:
            return _zstandard.ZstdCompressor().compress(data)

        @staticmethod
        def decompress(data: bytes) -> bytes:
            return _zstandard.ZstdDecompressor().decompress(data)

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from trade_pipeline.common.db_models import Trade

DEFAULT_BATCH_SIZE = 1000


@dataclass(frozen=True, slots=True)
class ArchiveResult:
    archived_count: int
    archive_path: Path | None
    uncompressed_bytes: int
    compressed_bytes: int

    @property
    def compression_ratio(self) -> float:
        if self.compressed_bytes == 0:
            return 0.0
        return self.uncompressed_bytes / self.compressed_bytes


def _serialize_trade(trade: Trade) -> dict:
    return {
        "broker_id": trade.broker_id,
        "trade_id": trade.trade_id,
        "symbol": trade.symbol,
        "qty": trade.qty,
        "price": str(trade.price),
        "timestamp": trade.timestamp.isoformat(),
    }


def archive_pending_trades(
    session: Session,
    archive_dir: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> ArchiveResult:
    """Archive up to `batch_size` not-yet-archived trades.

    Rows are only marked `archived=True` after the compressed file has been
    written successfully — if this crashes mid-run before that commit, the
    same rows are simply picked up again by the next run. No rows are ever
    marked archived without a corresponding file on disk.
    """
    pending = session.scalars(
        select(Trade).where(Trade.archived.is_(False)).order_by(Trade.id).limit(batch_size)
    ).all()

    if not pending:
        return ArchiveResult(
            archived_count=0, archive_path=None, uncompressed_bytes=0, compressed_bytes=0
        )

    payload = json.dumps([_serialize_trade(t) for t in pending]).encode("utf-8")
    compressed = zstd.compress(payload)

    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    archive_path = archive_dir / f"trades_{timestamp}_{len(pending)}.json.zst"
    archive_path.write_bytes(compressed)

    ids = [t.id for t in pending]
    session.execute(update(Trade).where(Trade.id.in_(ids)).values(archived=True))
    session.commit()

    return ArchiveResult(
        archived_count=len(pending),
        archive_path=archive_path,
        uncompressed_bytes=len(payload),
        compressed_bytes=len(compressed),
    )


def read_archived_batch(archive_path: Path) -> list[dict]:
    """Decompress and parse one archive file — used by tests and by any
    future reader (e.g. the T-13 aggregation job) rather than duplicating
    the zstd + JSON round-trip logic at each call site.
    """
    compressed = archive_path.read_bytes()
    payload = zstd.decompress(compressed)
    return json.loads(payload)


__all__ = ["ArchiveResult", "archive_pending_trades", "read_archived_batch"]
