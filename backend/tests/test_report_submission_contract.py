import json
from uuid import uuid4
import pytest
from pydantic import ValidationError
from finops_agent.agents_v2.report_contract import SaveReportInput
from finops_agent.agents_v2.registry import ORCHESTRATOR
from finops_agent.chat.models import ChatMessage
from finops_agent.chat.store import ChatStore
from finops_agent.chat.tools import chat_tools
from finops_agent.engine.run_audit import RunAuditStore
from test_agents_v2_flow import call
from test_chat_graph import wait_job


def payload():
    return dict(
        report=dict(clientId="acme", currency="USD", period="2026-10"),
        summary=dict(totalSpend=100),
        findings=[dict(id="F-1", title="Presupuesto", usdImpactMonthly=12)],
        tickets=dict(
            snapshot=[],
            proposedActions=[
                dict(
                    action="create",
                    ticket=dict(id="HTS-1", usdImpactMonthly=12, verification=dict(expect="< 100", window="14d")),
                ),
                dict(action="create", ticket=dict(id="HTS-2", usdImpactMonthly=3)),
            ],
            verificationResults=[],
        ),
    )


@pytest.mark.parametrize("encoding", ["native", "text", "fenced", "missing_action_braces"])
def test_report_input_normalizes_without_losing_values(encoding):
    original = payload()
    value = original if encoding == "native" else json.dumps(original)
    if encoding == "fenced":
        value = "```json\n" + value + "\n```"
    if encoding == "missing_action_braces":
        value = value.replace('}}}, {"action"', '}}, {"action"')
    parsed = SaveReportInput.model_validate(dict(markdown="# Informe\n\nResumen", structured_report=value))
    assert parsed.structured_report.model_dump(exclude_unset=True) == original
    assert parsed.markdown == "# Informe\n\nResumen"


@pytest.mark.parametrize(
    "value",
    [
        "not JSON",
        "[]",
        '{"findings": }',
        '{"summary":{"totalSpend":1,"totalSpend":2}}',
        '{"summary":{"totalSpend":NaN}}',
    ],
)
def test_ambiguous_or_value_inventing_repairs_are_rejected(value):
    with pytest.raises(ValidationError):
        SaveReportInput.model_validate(dict(markdown="# Informe", structured_report=value))


@pytest.mark.asyncio
async def test_typed_tool_saves_both_files_on_first_malformed_legacy_call(container, csv_path):
    client = container.client("acme")
    client.engine.ingest_focus_csv("acme", csv_path)
    store = ChatStore(client)
    thread = store.create(ORCHESTRATOR)
    thread.update(turn_id="test", ticket_refs=[])
    store.save(thread)
    tools = {t.name: t for t in chat_tools(container, "acme", thread["thread_id"], "test")}
    text = json.dumps(payload()).replace('}}}, {"action"', '}}, {"action"')
    result = await tools["save_report"].ainvoke(dict(markdown="# Informe\n\nResumen", structured_report=text))
    assert result["status"] == "saved"
    key = result["run_id"]
    saved_text = (client.workspace / "reports" / (key + ".md")).read_text()
    assert saved_text.startswith("# Informe\n\nResumen") and 'Próximas acciones y seguimiento' in saved_text
    saved = json.loads((client.workspace / "reports" / (key + ".json")).read_text())
    assert {k:v for k,v in saved.items() if k!='consulting'} == payload()
    assert saved['consulting']['agenda_revision']
    assert RunAuditStore(client.workspace).read(key)["input_normalization"] == "syntax_repaired"
    schema = tools["save_report"].args_schema.model_json_schema()
    assert schema["properties"]["structured_report"].get("$ref")


@pytest.mark.asyncio
async def test_failed_submission_is_compact_and_stops_after_two_attempts(container):
    class Model:
        calls = 0

        async def complete(self, messages, tools):
            self.calls += 1
            assert self.calls <= 2
            return call(
                "save_report", dict(markdown="# DO_NOT_ECHO " + ("long draft " * 100), structured_report="not JSON")
            )

    container.llm = Model()
    store = ChatStore(container.client("acme"))
    thread = store.create(ORCHESTRATOR)
    container.chat.start("acme", thread["thread_id"], ChatMessage(text="Informe", message_id=uuid4().hex))
    final = await wait_job(container, thread)
    assert final["status"] == "error" and "dos intentos" in final["error"]
    errors = [a["result"]["error"] for a in final["activity"] if a["tool"] == "save_report"]
    assert len(errors) == 2 and all(len(e) < 800 and "DO_NOT_ECHO" not in e for e in errors)


@pytest.mark.asyncio
async def test_successful_receipt_is_reused_before_revalidating_a_repeat(container, csv_path):
    client = container.client("acme")
    client.engine.ingest_focus_csv("acme", csv_path)

    class Model:
        calls = 0

        async def complete(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return call("save_report", dict(markdown="# Informe", structured_report=payload()))
            if self.calls == 2:
                return call("save_report", dict(markdown="", structured_report="invalid duplicate"))
            return dict(message=dict(role="assistant", content="Informe guardado."))

    container.llm = Model()
    store = ChatStore(client)
    thread = store.create(ORCHESTRATOR)
    container.chat.start("acme", thread["thread_id"], ChatMessage(text="Informe", message_id=uuid4().hex))
    final = await wait_job(container, thread)
    assert final["status"] == "ready", final.get("error")
    receipts = [a["result"] for a in final["activity"] if a["tool"] == "save_report"]
    assert len(receipts) == 2 and receipts[0]["run_id"] == receipts[1]["run_id"] and receipts[1]["reused"]
    assert len(RunAuditStore(client.workspace).list()) == 1


def test_old_report_validation_loops_are_not_replayed_into_new_model_context():
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from finops_agent.chat.message_history import complete_history
    args=dict(markdown='obsolete long draft',structured_report='invalid')
    messages=[HumanMessage(content='Informe'),AIMessage(content='',tool_calls=[dict(id='old',name='save_report',args=args)]),
        ToolMessage(content='old validation error',name='save_report',tool_call_id='old',status='error'),
        HumanMessage(content='Corrige el informe'),AIMessage(content='',tool_calls=[dict(id='new',name='save_report',args=args)]),
        ToolMessage(content='current compact error',name='save_report',tool_call_id='new',status='error')]
    result=complete_history(messages)
    assert not any(isinstance(m,ToolMessage) and m.tool_call_id=='old' for m in result)
    assert any(isinstance(m,ToolMessage) and m.tool_call_id=='new' for m in result)
