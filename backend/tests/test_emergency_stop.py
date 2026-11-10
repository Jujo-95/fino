import asyncio
from uuid import uuid4
import pytest
from finops_agent.api.control_routes import stop_report
from finops_agent.chat.store import ChatStore
from finops_agent.chat.models import ChatMessage
from finops_agent.agents_v2.registry import ORCHESTRATOR
from finops_agent.engine.run_audit import RunAuditStore
from test_agents_v2_flow import call


@pytest.mark.asyncio
async def test_stop_cancels_active_stream_and_allows_new_message(container):
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    class Model:
        calls = 0

        async def complete(self, *args):
            raise AssertionError("Must stream")

        async def stream_complete(self, messages, tools, on_text):
            self.calls += 1
            if self.calls > 1:
                return dict(message=dict(role="assistant", content="Nueva respuesta."))
            await on_text("Avance parcial.")
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    container.llm = Model()
    store = ChatStore(container.client("acme"))
    thread = store.create()
    container.chat.start("acme", thread["thread_id"], ChatMessage(text="Analiza", message_id=uuid4().hex))
    await asyncio.wait_for(entered.wait(), 5)
    stopped = await container.chat.stop("acme", thread["thread_id"])
    assert cancelled.is_set() and stopped["status"] == "cancelled"
    assert stopped["messages"][-1]["content"] == "Avance parcial."
    assert stopped["messages"][-1]["interrupted"]
    container.chat.start("acme", thread["thread_id"], ChatMessage(text="Hola otra vez", message_id=uuid4().hex))
    await container.chat.tasks["acme:" + thread["thread_id"]]
    history = store.read(thread["thread_id"])["messages"]
    assert history[-1]["content"] == "Nueva respuesta."
    assert any(m["content"]=="Avance parcial." and m["interrupted"] for m in history)



def delegated_model(entered, cancelled):
    class Model:
        async def complete(self, messages, tools):
            names = {t["function"]["name"] for t in tools}
            if "save_report" not in names:
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
            if messages[-1]["role"] == "user":
                return call("start_report_job", {})
            return call(
                "consult_specialist", dict(specialist="v2-budget-anomaly-operator", question="Analiza el gasto")
            )

    return Model()

@pytest.mark.asyncio
async def test_stop_report_cancels_delegated_specialist_and_checks_tenant(container, csv_path):
    client = container.client("acme")
    client.engine.ingest_focus_csv("acme", csv_path)
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    container.llm = delegated_model(entered, cancelled)
    store = ChatStore(client)
    thread = store.create(ORCHESTRATOR)
    container.chat.start("acme", thread["thread_id"], ChatMessage(text="Informe", message_id=uuid4().hex))
    await asyncio.wait_for(entered.wait(), 5)
    key = store.read(thread["thread_id"])["report_run_id"]
    from finops_agent.models import ClientProfile

    container.onboard(ClientProfile(client_id="other", client_name="Other"))
    with pytest.raises(KeyError):
        await stop_report("other", key, container)
    result = await stop_report("acme", key, container)
    assert result["status"] == "cancelled" and cancelled.is_set()
    assert store.read(thread["thread_id"])["status"] == "cancelled"
    import json

    children = [
        json.loads(p.read_text()) for p in store.directory.glob("*.json") if json.loads(p.read_text()).get("internal")
    ]
    assert len(children) == 1 and children[0]["status"] == "cancelled"
    assert RunAuditStore(client.workspace).read(key)["status"] == "cancelled"
