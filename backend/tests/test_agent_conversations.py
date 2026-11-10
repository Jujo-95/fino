from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from finops_agent.api.server import app
from finops_agent.api.routes import get_container
from finops_agent.chat.store import ChatStore
from finops_agent.chat.agent_context import instructions
from finops_agent.chat.models import ChatMessage
from test_chat_graph import wait_job


class AgentDouble:
    async def complete(self, messages, tools):
        prompt = messages[0]["content"]
        assert "especialista Allocation" in prompt
        assert "consult_specialist" not in str(tools)
        return {"message": {"role": "assistant", "content": "Revisaré las etiquetas con evidencia."}}


@pytest.mark.asyncio
async def test_specialist_uses_existing_graph_and_separate_history(container):
    client = container.client("acme")
    store = ChatStore(client)
    orchestrator = store.create()
    specialist = store.create("allocation")
    container.llm = AgentDouble()
    container.chat.start("acme", specialist["thread_id"], ChatMessage(text="Hola", message_id=uuid4().hex))
    ready = await wait_job(container, specialist)
    assert ready["status"] == "ready" and ready["agent_id"] == "allocation"
    assert not store.read(orchestrator["thread_id"])["messages"]
    assert len(store.list("allocation")) == 1
    assert store.list("allocation")[0]["title"] == "Hola"
    assert store.list("orchestrator")[0]["thread_id"] == orchestrator["thread_id"]
    with pytest.raises(ValueError):
        store.create("fake")


def test_agent_metadata_and_api_rate_limit(container):
    app.dependency_overrides[get_container] = lambda: container
    try:
        http = TestClient(app)
        base = "/api/v1/clients/acme/chat/threads"
        result = http.post(base, json={"agent_id": "anomaly"})
        assert result.status_code == 200 and result.json()["agent_id"] == "anomaly"
        assert len(http.get(base + "?agent_id=anomaly").json()) == 1
        assert not http.get(base + "?agent_id=budgeting").json()
        assert http.post(base, json={"agent_id": "fake"}).status_code == 422
        assert http.post(base, json={"agent_id": "anomaly", "audit_run_id": "a" * 32}).status_code == 404
        assert http.post(base, json={"agent_id": "anomaly"}).json()["thread_id"] == result.json()["thread_id"]
        store = ChatStore(container.client("acme"))
        for _ in range(19):
            created = http.post(base).json()
            created["messages"] = [{"role": "human", "content": "Consulta previa"}]
            store.save(created)
        blocked = http.post(base)
        assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "agent", ["allocation", "anomaly", "budgeting", "forecasting", "commitment", "orchestrator"]
)
def test_roles_reuse_versioned_prompts(agent):
    prompt = instructions(agent)
    assert len(prompt) > 100


def test_empty_conversation_creation_is_atomic_and_scoped(container):
    from concurrent.futures import ThreadPoolExecutor
    store = ChatStore(container.client("acme"))
    admitted = []
    def create():
        return store.get_or_create("orchestrator", None, lambda: admitted.append(True))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: create(), range(20)))
    assert len({item["thread_id"] for item in results}) == 1
    assert len(admitted) == 1
    first = results[0]
    first["messages"] = [{"role": "human", "content": "Hola"}]
    store.save(first)
    second = create()
    assert second["thread_id"] != first["thread_id"]
    store.set_archived(second["thread_id"], True)
    assert create()["thread_id"] != second["thread_id"]
    assert store.get_or_create("anomaly", None, lambda: None)["agent_id"] == "anomaly"
