# Feature: Dead-letter queue for the consumer

Status: shipped
Task: docs/tasks/completed/T-22-dead-letter-queue.md

## Problem / motivation

User asked for this directly. The current consumer (`consumer/dedup_consumer.py`) has a real gap: on
any processing failure (malformed message, transient DB error, anything), `run_consumer` logs and
`continue`s **without committing** — the "poison pill" problem. Within a single running process, Kafka
`poll()` still advances past the bad message (poll and commit are independent), so it doesn't actually
freeze the consumer live — but on every restart/rebalance, the consumer resumes from the last
*committed* offset and re-attempts the same failing message again, forever, for anything that fails
for a **permanent** reason (a message that will never successfully process no matter how many times
it's retried). The plan's own system-design guidance calls this out explicitly ("Kafka broker down →
consumer lag alert → DLQ fills → ops page") — this project didn't actually have a DLQ.

## Scope

In: `consumer/dlq.py` — a small wrapper publishing a failed message's envelope (original topic/
partition/offset, the error, and the raw payload) to a dead-letter topic (`{topic}-dlq`). Wired into
`run_consumer`: on a processing failure, publish to the DLQ *and then commit* the original offset —
trading "silently lose nothing, retry forever" for "capture it durably, keep the pipeline moving." A
Prometheus counter (`consumer_dlq_total`) for observability. A **replay tool**
(`replay_dlq`/`python -m trade_pipeline.consumer.dlq --topic trades`) reads envelopes back off the DLQ
topic and re-publishes each one's original payload to its original topic, so the normal consumer
reprocesses it — a deliberate batch tool a human runs on demand, not a background service.

Out:
- Automatic DLQ topic creation — matches this project's existing pattern of manually creating the
  `trades` topic (see `docs/walkthrough/02-producer.md`); a real deployment would provision this via
  infrastructure-as-code, not application code.
- Automatic/scheduled replay — replay is a deliberate, manually-triggered action (a human decides a
  batch of DLQ'd messages is now safe to reprocess, e.g. after fixing whatever caused them to fail);
  auto-replaying on a schedule risks looping a message that will fail identically every time.

## Design

- **Commit after DLQ publish, not skip-without-commit**: this is the actual behavior change. The old
  behavior ("redeliver forever") is correct for *transient* failures (a DB blip that will succeed on
  retry) but wrong for *permanent* ones (a message that can never be processed) — and the consumer
  can't always tell the difference cheaply. Publishing to the DLQ and committing anyway means a
  permanently-bad message stops generating repeated failures on every restart, while still being
  captured (not silently dropped) for a human to inspect or a replay tool to re-attempt later.
- **DLQ publish failure itself is not swallowed**: if publishing to the DLQ topic fails, the original
  offset is *not* committed — falling back to the old "retry on restart" behavior, which is still
  better than silently losing the message. This is a deliberate two-tier fallback, not an oversight.
- **Envelope format is plain JSON, not a schema registry entry**: matches this project's existing
  choice for the main `trades` topic (plain JSON, not Avro/Protobuf) — consistent, and avoids adding
  new infrastructure for one topic.

## Python version notes

No version-gated syntax; targets the full 3.11–3.14 range.

## Testing plan

- Pure-logic tests: a fake DLQ producer capturing calls, verifying a processing failure results in a
  DLQ publish with the correct envelope fields (error type, original topic/partition/offset, payload)
  and that the *original* offset is committed afterward (not skipped).
- A DLQ-publish-itself-fails case: confirms the original offset is *not* committed in that case (falls
  back to redelivery-on-restart, the safer failure mode when the DLQ itself is unavailable).
- No `dlq_producer` configured at all: confirms the pre-existing "skip without commit" behavior is
  unchanged (backward compatible — `dlq_producer` is optional).
- Existing `DedupConsumer`/`run_consumer` tests continue passing unchanged — DLQ wiring only changes
  behavior on the failure path, not the success path already covered.
- Verified end to end against real Kafka: published a message that fails processing, confirmed it
  lands on the `<topic>-dlq` topic with the expected envelope, then ran the replay tool and confirmed
  the original payload republishes to the original topic correctly.
