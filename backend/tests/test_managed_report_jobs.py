import asyncio
from uuid import uuid4
import pytest
from finops_agent.agents_v2.registry import ORCHESTRATOR
from finops_agent.chat.models import ChatMessage
from finops_agent.chat.store import ChatStore
from finops_agent.engine.run_audit import RunAuditStore
from test_agents_v2_flow import FleetDouble, call
from test_chat_graph import wait_job


class ManagedFleet(FleetDouble):
    async def complete(self, messages, tools):
        names = {item["function"]["name"] for item in tools}
        last = messages[-1]
        if "save_report" in names and last["role"] == "user":
            self.calls += 1
            return call("start_report_job", {})
        if last.get("name") == "start_report_job":
            self.calls += 1
            return call(
                "consult_specialist",
                dict(specialist="v2-budget-anomaly-operator", question="Valida costos del periodo."),
            )
        return await super().complete(messages, tools)


@pytest.mark.asyncio
async def test_chat_report_uses_one_registered_job_and_persists_artifacts(container, csv_path):
    client = container.client("acme")
    client.engine.ingest_focus_csv("acme", csv_path)
    container.llm = ManagedFleet()
    store = ChatStore(client)
    thread = store.create(ORCHESTRATOR)
    container.chat.start("acme", thread["thread_id"], ChatMessage(text="Prepara el informe", message_id=uuid4().hex))
    result = await wait_job(container, thread)
    assert result["status"] == "ready", result.get("error")
    runs = RunAuditStore(client.workspace)
    records = runs.list()
    assert len(records) == 1 and records[0]["status"] == "completed"
    assert result["report_run_id"] == records[0]["run_id"]
    saved = [a for a in result["activity"] if a["tool"] == "save_report"][0]["result"]
    assert saved["run_id"] == result["report_run_id"]
    assert runs.detail(saved["run_id"])["structured_report"]["client_id"] == "acme"
    assert (client.workspace / "reports" / (saved["run_id"] + ".md")).exists()
    assert not container.jobs.tasks and not container.jobs.records



def paused_model(started, release, outcome):
    class Model:
        calls = 0

        async def complete(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return call("start_report_job", {})
            started.set()
            await release.wait()
            if outcome == "failure":
                raise ValueError("explicit test failure")
            return dict(message=dict(role="assistant", content="Análisis sin entrega."))

    return Model()

@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["stop", "incomplete", "failure"])
async def test_report_registered_before_analysis_and_never_false_completed(container, csv_path, outcome):
    client = container.client("acme")
    client.engine.ingest_focus_csv("acme", csv_path)
    started = asyncio.Event()
    release = asyncio.Event()

    container.llm = paused_model(started, release, outcome)
    store = ChatStore(client)
    thread = store.create(ORCHESTRATOR)
    container.chat.start("acme", thread["thread_id"], ChatMessage(text="Prepara el informe", message_id=uuid4().hex))
    task = container.chat.tasks["acme:" + thread["thread_id"]]
    await asyncio.wait_for(started.wait(), 5)
    current = store.read(thread["thread_id"])
    key = current["report_run_id"]
    runs = RunAuditStore(client.workspace)
    assert runs.read(key)["status"] == "running" and container.jobs.tasks[key] is task
    if outcome == "stop":
        result = await container.chat.stop("acme", thread["thread_id"])
        assert result["status"] == "cancelled"
        assert (await container.chat.stop("acme", thread["thread_id"]))["status"] == "cancelled"
    else:
        release.set()
        await task
    record = runs.read(key)
    assert record["status"] == ("cancelled" if outcome == "stop" else "failed")
    assert not record["report_markdown"] and not container.jobs.tasks
    assert list(client.workspace.glob("reports/*.md")) == []
