# 04 — Autonomous Implementation Playbook (Zero-to-Production)

> **Instructions for any AI Agent on a new machine**:
> Follow these 5 phases in exact order. Before writing any file, execute the **Pre-Flight Protocol** in `AGENTS.md` (read the corresponding `.cursor/skills/finops-build-*/SKILL.md` and cite the FinOps Capability from `finops_capabilities_md/capabilities/<slug>.md`).
> Keep every file `<= 180` lines and every function `<= 35` lines.

---

## Target Repository Tree

```text
finops-agent-app/
├── AGENTS.md
├── docs/
│   ├── 01-PRODUCT-AND-DOMAIN-SPEC.md
│   ├── 02-DATA-AND-MEMORY-SCHEMAS.md
│   ├── 03-AGENT-AND-API-CONTRACTS.md
│   └── 04-IMPLEMENTATION-PLAYBOOK.md
├── finops_capabilities_md/              # Local copy of all 22 FinOps Foundation capabilities
├── .cursor/
│   ├── rules/                           # 5 mandatory .mdc guardrails
│   └── skills/                          # 6 stack & domain skills
├── backend/
│   ├── pyproject.toml
│   ├── src/finops_agent/
│   │   ├── __init__.py
│   │   ├── config.py                    # Env config + atomic_write_text + make_fingerprint
│   │   ├── models.py                    # Immutable Pydantic v2 models & FinOpsGraphState
│   │   ├── engine/
│   │   │   ├── duckdb_engine.py         # Transactional FOCUS CSV loader + sqlglot AST guard
│   │   │   ├── kpi_catalog.py           # Declarative SQL catalog for the 13 FinOps KPIs
│   │   │   ├── hipporag_memory.py       # Dual HippoRAG graph (KB + Client Personalized PageRank)
│   │   │   └── ticket_manager.py        # 3-step atomic Unit-of-Work (.md + DuckDB + HippoRAG)
│   │   ├── agents/
│   │   │   ├── specs.py                 # Declarative SpecialistSpec for all 5 specialists
│   │   │   ├── runner.py                # Single DRY SpecialistRunner + LLMProviderFactory
│   │   │   └── orchestrator.py          # LangGraph StateGraph wiring + report synthesizer
│   │   └── api/
│   │       ├── container.py             # Lifespan singleton resource container
│   │       └── server.py                # FastAPI routes + SSE graph stream
│   └── tests/
│       ├── conftest.py                  # Synthetic FOCUS CSV generator & temp workspace fixture
│       ├── test_duckdb_and_kpis.py      # Table-driven SQL AST & idempotent ingestion tests
│       ├── test_atomic_memory.py        # Ticket deduplication & HippoRAG multi-hop recall tests
│       └── test_orchestrator_e2e.py     # Full onboarding -> daily run -> ticket feedback loop test
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── types.ts
        ├── hooks/useSSEStream.ts
        ├── components/Primitives.tsx    # Reusable KpiMetricCard, MaturityBadge, TicketCard
        └── App.tsx                      # 4-tab FinOps Console (Onboarding, Live Run, KPIs, Tickets)
```

---

## Step-by-Step Build Phases & Verification Gates

### Phase 1: Backend Foundation, Models & DuckDB FOCUS Engine
1. **Read Skill**: `.cursor/skills/finops-build-duckdb-engine/SKILL.md`
2. **Create**:
   - `backend/pyproject.toml` (`duckdb`, `sqlglot`, `pydantic>=2.8`, `fastapi`, `uvicorn`, `langgraph`, `langchain-core`, `pyyaml`, `networkx`, `httpx`, `pytest`, `pytest-asyncio`, `ruff`, `mypy`)
   - `backend/src/finops_agent/config.py`
   - `backend/src/finops_agent/models.py`
   - `backend/src/finops_agent/engine/duckdb_engine.py`
   - `backend/src/finops_agent/engine/kpi_catalog.py`
   - `backend/tests/conftest.py` & `backend/tests/test_duckdb_and_kpis.py`
3. **Verify Gate**: `uv run pytest backend/tests/test_duckdb_and_kpis.py` passes 100% (verifying idempotent CSV ingestion and `sqlglot` AST rejection of unsafe queries).

### Phase 2: Dual HippoRAG Knowledge Graph & Atomic Ticket Memory
1. **Read Skill**: `.cursor/skills/finops-build-atomic-memory/SKILL.md`
2. **Create**:
   - `backend/src/finops_agent/engine/hipporag_memory.py` (Entity-relation graph + Personalized PageRank associative retrieval over `finops_capabilities_md` and client tickets/notes).
   - `backend/src/finops_agent/engine/ticket_manager.py` (3-step atomic commit: `.tmp -> os.replace` Markdown + DuckDB `tickets_ledger` + HippoRAG node upsert).
   - `backend/tests/test_atomic_memory.py`
3. **Verify Gate**: `uv run pytest backend/tests/test_atomic_memory.py` passes 100% (verifying zero duplicate tickets on repeated runs and associative recall of resolved/false-positive tickets).

### Phase 3: DRY LangGraph Specialist Fleet & Orchestrator
1. **Read Skill**: `.cursor/skills/finops-build-langgraph-fleet/SKILL.md`
2. **Create**:
   - `backend/src/finops_agent/agents/specs.py`
   - `backend/src/finops_agent/agents/runner.py`
   - `backend/src/finops_agent/agents/orchestrator.py`
   - `backend/tests/test_orchestrator_e2e.py`
3. **Verify Gate**: `uv run pytest backend/tests/test_orchestrator_e2e.py` passes 100% (verifying that an anomaly marked as `FALSE_POSITIVE` in a ticket suppresses future anomaly alerts and excludes that spike from CUD/Savings Plan commitment recommendations).

### Phase 4: FastAPI Server, Lifespan Container & SSE Streaming
1. **Read Skill**: `.cursor/skills/finops-build-fastapi-sse/SKILL.md`
2. **Create**:
   - `backend/src/finops_agent/api/container.py`
   - `backend/src/finops_agent/api/server.py`
3. **Verify Gate**: Full backend test suite + typecheck + lint (`uv run pytest && uv run ruff check backend/`).

### Phase 5: Lean React + TypeScript Dashboard
1. **Read Skill**: `.cursor/skills/finops-build-lean-ui-tests/SKILL.md`
2. **Create**:
   - `frontend/` files (`package.json`, `src/types.ts`, `src/hooks/useSSEStream.ts`, `src/components/Primitives.tsx`, `src/App.tsx`).
3. **Verify Gate**: `npm --prefix frontend run build` succeeds with zero TypeScript errors.
