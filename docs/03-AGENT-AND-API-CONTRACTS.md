# 03 — Agent, API & UI Contracts

## 1. LangGraph State & Pydantic Domain Models (`backend/src/finops_agent/models/`)

All models use `model_config = ConfigDict(frozen=True)`.

```python
from typing import Literal, TypedDict
from pydantic import BaseModel, ConfigDict, Field

MaturityTier = Literal["Crawl", "Walk", "Run"]
AllocationMode = Literal["Showback", "Chargeback", "N/A"]
TicketStatus = Literal["PROPOSED", "APPROVED", "IMPLEMENTED", "REJECTED", "FALSE_POSITIVE", "SNOOZED"]
Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)
    capability: str
    maturity_tier: MaturityTier
    allocation_mode: AllocationMode
    severity: Severity
    sub_account_id: str
    service_name: str
    period_bucket: str
    kpi_name: str
    kpi_value: float
    estimated_monthly_impact_usd: float
    title: str
    evidence_summary: str
    recommended_action: str
    capability_citation_url: str

class FinOpsGraphState(TypedDict):
    client_id: str
    run_mode: Literal["onboarding", "daily"]
    period_start_utc: str
    period_end_utc: str
    billing_currency: str
    ingested_rows: int
    kpi_snapshots: dict[str, list[dict[str, object]]]
    active_anomalies: list[str]          # SubAccountId:ServiceName keys with active spikes
    findings: list[Finding]
    emitted_tickets: list[str]           # Ticket IDs created or updated
    report_markdown: str
```

## 2. FastAPI REST & SSE Endpoints (`backend/src/finops_agent/api/`)

| Method | Path | Purpose | Request / Response Contract |
|---|---|---|---|
| `GET` | `/api/v1/health` | Liveness & DuckDB/HippoRAG readiness | `{"status": "ok", "duckdb": true, "hipporag_kb_nodes": int}` |
| `POST` | `/api/v1/clients/onboard` | Create/update `client_profile.yaml`, upload initial FOCUS CSVs & context notes | `Multipart/JSON` -> returns `ClientSummary` + ingested row count |
| `GET` | `/api/v1/clients/{client_id}/overview` | Return current KPIs, budget burn rate, ESR, unallocated % | Returns `ClientDashboardOverview` |
| `POST` | `/api/v1/runs/stream` | Execute LangGraph Orchestrator (`onboarding` or `daily`) streaming SSE per node | Streams `data: {"node": "<name>", "payload": {...}}\n\n` |
| `GET` | `/api/v1/clients/{client_id}/tickets` | List tickets from `tickets_ledger` filtered by `status` or `capability` | Returns `list[FinOpsTicket]` |
| `PATCH` | `/api/v1/clients/{client_id}/tickets/{ticket_id}` | Update `status` & `resolution_note` atomically (`.md` + DuckDB + HippoRAG) | Body: `{"status": TicketStatus, "resolution_note": str}` |
| `GET` | `/api/v1/clients/{client_id}/reports` | List and read generated Markdown FinOps reports | Returns `list[ReportDocument]` |

## 3. Multi-Provider Environment Configuration (`.env.example`)
```ini
FINOPS_WORKSPACES_DIR=./workspaces
FINOPS_KB_DIR=./finops_capabilities_md/capabilities
FINOPS_LLM_PROVIDER=anthropic          # anthropic | openai | vertex | mock
FINOPS_LLM_MODEL=claude-sonnet-4-5     # or gpt-4o / gemini-2.5-pro
FINOPS_EMBEDDING_PROVIDER=openai       # openai | vertex | local_hash
FINOPS_EMBEDDING_MODEL=text-embedding-3-small
```
*Note*: Include a deterministic `mock` / rule-assisted fallback mode in `LLMProviderFactory` and `local_hash` / TF-IDF graph embeddings in `DualHippoRAGService` so the entire application, tests, and local UI work **offline with zero external API keys** when desired, while seamlessly switching to Anthropic/OpenAI/Vertex when keys are set.

## 4. Lean React Frontend Views (`frontend/src/`)
1. **`OnboardingView.tsx`**: Client profile editor + FOCUS CSV drag-and-drop uploader.
2. **`OrchestratorStreamView.tsx`**: Triggers `/api/v1/runs/stream`, renders step-by-step live badges (`ingest` -> `allocation` -> `anomaly` -> `forecasting` -> `budgeting` -> `commitment` -> `synthesize`), and displays the generated Markdown report.
3. **`KpiMatrixView.tsx`**: Renders `<KpiMetricCard />` across all 13 FinOps Foundation KPIs with `Showback` / `Chargeback` and `Crawl` / `Walk` / `Run` badges.
4. **`TicketsKanbanView.tsx`**: Interactive columns (`PROPOSED`, `APPROVED`, `IMPLEMENTED`, `FALSE_POSITIVE`) where changing status + adding a resolution note immediately updates HippoRAG memory.
