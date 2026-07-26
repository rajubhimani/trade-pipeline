"""Daily aggregation over archived cold-storage batches.

Reads every archived batch file under ``archive/`` and computes simple
rollups (volume per broker, count per symbol) — a downstream Dagster asset
depending on the archival asset (T-8), not a standalone job, since it only
makes sense to run after there's something archived to aggregate.

Deliberately does NOT compute "dedup hit rate" despite that being named in
the original backlog note: archived files only ever contain trades that
already passed Redis dedup (T-4) — duplicates are dropped before ever
reaching Postgres or the archive, so there's no duplicate-vs-unique ratio
left to recover from this data. That's already tracked correctly, from the
right data, by the consumer's own dedup_hits_total/dedup_misses_total
Prometheus counters (T-7). See docs/features/dagster-aggregation.md.
"""

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from trade_pipeline.dagster_pipeline.archival import read_archived_batch


@dataclass(frozen=True, slots=True)
class AggregationResult:
    total_trades: int
    volume_by_broker: dict[str, int]
    count_by_symbol: dict[str, int]
    output_path: Path | None


def aggregate_archive_directory(
    archive_dir: Path, output_dir: Path | None = None
) -> AggregationResult:
    """Aggregate every `*.json.zst` file directly under `archive_dir`.

    Reads the whole directory every run rather than tracking a
    high-water-mark of already-aggregated files — appropriate for a daily
    job over a modest number of files; contrast with the archival job
    itself (T-8), which does need incremental tracking since it runs every
    minute against a live, constantly-growing table.
    """
    archive_files = sorted(archive_dir.glob("*.json.zst"))

    volume_by_broker: Counter[str] = Counter()
    count_by_symbol: Counter[str] = Counter()
    total_trades = 0

    for path in archive_files:
        for trade in read_archived_batch(path):
            total_trades += 1
            volume_by_broker[trade["broker_id"]] += trade["qty"]
            count_by_symbol[trade["symbol"]] += 1

    output_path = None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        output_path = output_dir / f"aggregate_{timestamp}.json"
        output_path.write_text(
            json.dumps(
                {
                    "total_trades": total_trades,
                    "volume_by_broker": dict(volume_by_broker),
                    "count_by_symbol": dict(count_by_symbol),
                }
            )
        )

    return AggregationResult(
        total_trades=total_trades,
        volume_by_broker=dict(volume_by_broker),
        count_by_symbol=dict(count_by_symbol),
        output_path=output_path,
    )


__all__ = ["AggregationResult", "aggregate_archive_directory"]
