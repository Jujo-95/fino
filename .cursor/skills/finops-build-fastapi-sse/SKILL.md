---
name: finops-build-fastapi-sse
description: Build and extend the FastAPI backend, multi-provider LLM configuration, lifespan resource pool, and Server-Sent Events (SSE) streaming endpoints. Use whenever working on API routes, SSE streaming, dependency injection, or LLM provider adapters.
---

# FinOps FastAPI & Multi-Provider SSE Skill

## Capabilities Covered
- `@finops_capabilities_md/capabilities/automation-tools-services.md` (https://www.finops.org/framework/capabilities/automation-tools-services/)

## Core Blueprint

### 1. Single Lifespan Resource Pool (Zero Per-Request Instantiation)
Initialize `DuckDBFocusEngine`, `DualHippoRAGService`, `AtomicTicketMemoryManager`, and `LLMProviderFactory` once in FastAPI's `lifespan` context manager and inject via `Depends(get_container)`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    container = AppContainer.from_env()
    app.state.container = container
    try:
        yield
    finally:
        await container.aclose()
```

### 2. Multi-Provider Agnostic LLM Factory
Resolve Anthropic, OpenAI, or Google Vertex AI from environment config in < 25 lines without hardcoding models in agents:

```python
def create_chat_model(cfg: LLMSettings) -> BaseChatModel:
    match cfg.provider:
        case "anthropic":
            return ChatAnthropic(model=cfg.model_name, temperature=0)
        case "openai":
            return ChatOpenAI(model=cfg.model_name, temperature=0)
        case "vertex":
            return ChatVertexAI(model=cfg.model_name, temperature=0)
        case _:
            raise ValueError(f"Unsupported LLM provider: {cfg.provider}")
```

### 3. Clean Server-Sent Events (SSE) Graph Streamer
Stream every LangGraph super-step (`allocation`, `anomaly`, `forecasting`, `budgeting`, `commitment`, `synthesize`) to the UI and check `await request.is_disconnected()` on each step (inspired by `MachineLearning/agent-orchestrator`):

```python
async def stream_finops_run(request: Request, graph, initial_state: FinOpsGraphState):
    async for event in graph.astream(initial_state, stream_mode="updates"):
        if await request.is_disconnected():
            break
        node_name, payload = next(iter(event.items()))
        yield f"data: {json.dumps({'node': node_name, 'payload': payload}, default=str)}\n\n"
    yield "data: {\"node\": \"__done__\"}\n\n"
```
