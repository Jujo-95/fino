# Report jobs from chat and emergency stop

Implemented 2026-10-21 by extending the existing ChatJobs, RunJobs, RunAuditStore and LangGraph flow.

## Report tool and lifecycle

Orchestrators expose `start_report_job`. For agents 2.0 the tool registers the already server-owned chat task in the existing report job registry, persists an audit record immediately and links its run ID to the conversation. It does not launch a competing graph or regenerate specialist work. Duplicate starts in one turn reuse the ID; another active report for the same client is rejected. Existing report rate limits apply.

The same orchestrator continues its queries, delegated specialists and streamed narrative. `save_report` writes Markdown, JSON and the audit under the registered run ID. Completion is recorded only after the artifacts are written. Ending without a saved report marks the job failed; cancellation marks it cancelled. The registered period remains fixed when saving. The original orchestrator's tool starts its existing fixed report pipeline instead.

Report history, SSE, exports and cancellation use the existing tenant-scoped run endpoints. The browser discovers jobs started from chat without navigating away. Chat displays a job link/status and Reportes displays progress and a stop action. Source prompts remain intact; the integration adapter requires starting the tool before report analysis.

## Cancellation

- `POST /api/v1/clients/{client_id}/chat/threads/{thread_id}/stop`
- `POST /api/v1/clients/{client_id}/runs/{run_id}/stop`

Both validate the resource within the selected client. Repeated stops are idempotent; completed runs retain their result. Cancelling a 2.0 report invokes the same root chat task cancellation. Async cancellation propagates through awaited delegated graphs, provider calls and queues. The existing HTTP streaming context closes; retry policy does not retry CancelledError.

The square button replaces Send while the chat runs. A report can also be stopped from its chat job tile or Reportes. Partial visible text is persisted in the LangGraph checkpoint as interrupted, and a later message can continue in the same conversation. Unanswered tool-call pairs are removed from model input after an interrupted tool round. Existing notes/changes already applied are not undone.

Cancellation stops app-side execution and prevents subsequent model calls. It cannot guarantee that NVIDIA aborts or refunds computation for a request already received. This MVP is per-execution cancellation, not a global kill switch. Reports and checkpoints survive browser refresh; process restart remains an interruption, not an external queue with automatic worker recovery.

## Verification

181 backend tests passed, including managed-job persistence, no false completion, cancellation during streaming and specialist delegation, continuation after stopping, tenant isolation and HTTP stop idempotency. Targeted cancellation tests were rerun after final checkpoint/period changes. Frontend build, Ruff and mypy pass.

An isolated UI instance with explicit synthetic data/model double verified: a chat report appears in Reportes before completion; refreshing preserves execution; Stop ends the task; Reportes shows Detenido; the composer becomes available again. No new NVIDIA calls were used for verification.

The user explicitly authorized stopping the pre-existing execution to activate this version. That conversation and its specialist were marked cancelled, with available messages/checkpoints preserved, before restarting the main backend.
