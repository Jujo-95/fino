# Backend task: exclusive, recoverable analysis jobs

Status: proposed; not implemented. No LLM calls or cloud mutations are required for acceptance.
Capability: [Automation, Tools & Services](https://www.finops.org/framework/capabilities/automation-tools-services/).

## Current behavior and reproducible defect

The canonical analysis produces structured results and ticket follow-up through `AnalysisJobs`.
An external entry point exists, but the application remains designed around local persistence.

`AnalysisQueue.__init__` changes every `running` job to `queued` whenever another queue connection opens.
Reproduction with two connections to a temporary SQLite file:

1. Connection A enqueues and claims one job: its persisted state becomes `running`.
2. Open connection B against the same queue: the job becomes `queued`.
3. B claims the same job while A still owns its execution.

Additionally, `AnalysisJobs.start` starts an embedded worker regardless of external-worker mode.
Cancellation uses process-local events; an external worker cannot rely on them alone.

## Deliverable

Extend the existing queue with explicit ownership and bounded recovery. Keep the existing analysis engine,
ticket operations, API payloads and UI. Do not introduce Redis, Celery or a second analysis engine.
The SQLite implementation remains a single-host pilot; this task does not certify distributed DuckDB writes.

## Implementation checklist

- [ ] Opening a queue connection never resets another worker's active jobs.
- [ ] A claimed job has an owner, lease expiry, heartbeat and monotonically increasing attempt token.
- [ ] Heartbeats extend ownership while a long query or model call is in progress.
- [ ] Recover only expired claims, transactionally; a stale attempt cannot finalize or mutate ticket state.
- [ ] Enforce ownership before side effects and preserve existing ticket deduplication and receipts.
- [ ] External mode enqueues work without starting an embedded execution loop.
- [ ] Persist cancellation; the owner checks it between stages and interrupts a query where supported.
- [ ] Expose safe audit fields: owner, attempt, stage, timestamps, cancellation and recovery reason.
- [ ] Keep successful stage results available for idempotent recovery; do not promise exactly-once model billing.

## Acceptance matrix the owner can audit

| Scenario | Required result |
| --- | --- |
| Open connection B while A executes | State remains running; B cannot claim A's live job. |
| Submit the same daily analysis twice | One job identity and one set of resulting tickets. |
| Simulate heartbeat expiry | Exactly one new owner can claim recovery. |
| Old owner finishes after recovery | Stale completion and ticket mutations are rejected. |
| Slow operation exceeds a heartbeat interval | Ownership remains live while heartbeats arrive. |
| External mode receives a manual request | Job is queued; no embedded worker is created. |
| API requests cancellation of an external job | Persisted request is observed; no subsequent stages start. |
| Reopen after explicit cancellation | Cancelled work is not automatically requeued. |
| Inspect job history | Stage, attempts and recovery cause are visible without secrets. |

Use temporary fixtures and two independent processes/connections where applicable. Simulate failure with a
controlled clock and fake adapters. Report measured test outcomes, not only a screenshot or model response.

## Other production gaps

- Chat execution is still an in-process asyncio task despite persisted LangGraph checkpoints.
- Multi-user authentication and tenant authorization are not production-ready.
- Cloud-action adapters currently simulate; approval does not execute a real cloud change.
- Operational data still spans DuckDB, SQLite and local files; Supabase migration remains pending.
- Cloud connectors need acceptance against authorized real buckets/tables before production certification.
