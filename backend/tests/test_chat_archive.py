from copy import deepcopy
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from finops_agent.api.server import app
from finops_agent.api.routes import get_container
from finops_agent.chat.store import ChatStore
from finops_agent.chat.models import ChatMessage
from finops_agent.models import ClientProfile


def test_archive_is_reversible_idempotent_and_preserves_messages(container):
    store = ChatStore(container.client("acme"))
    original = store.create("allocation")
    original["messages"] = [dict(id=uuid4().hex, role="human", content="Validar etiquetas")]
    original["pending"] = [dict(plan_id="preserved-plan")]
    store.save(original)
    before = deepcopy(store.read(original["thread_id"]))
    archived = store.set_archived(original["thread_id"], True)
    assert archived["archived"] and archived["archived_at"]
    assert not store.list("allocation")
    assert store.list("allocation", True)[0]["title"] == "Validar etiquetas"
    assert ChatStore(container.client("acme")).read(original["thread_id"])["archived"]
    assert store.set_archived(original["thread_id"], True)["updated_at"] == archived["updated_at"]
    with pytest.raises(ValueError, match="Restaura"):
        container.chat.start(
            "acme", original["thread_id"], ChatMessage(text="Continuar", message_id=uuid4().hex)
        )
    restored = store.set_archived(original["thread_id"], False)
    assert not restored["archived"] and restored["archived_at"] is None
    assert restored["messages"] == before["messages"] and restored["pending"] == before["pending"]
    assert len(store.list("allocation")) == 1 and not store.list("allocation", True)


def test_archive_http_tenant_scope_and_running_conflict(container):
    store = ChatStore(container.client("acme"))
    thread = store.create("anomaly")
    container.onboard(ClientProfile(client_id="another", client_name="Another"))
    app.dependency_overrides[get_container] = lambda: container
    base = "/api/v1/clients/acme/chat/threads"
    url = base + "/" + thread["thread_id"] + "/archive"
    try:
        http = TestClient(app)
        key = "acme:" + thread["thread_id"]
        container.chat.tasks[key] = object()
        assert http.patch(url, json={"archived": True}).status_code == 409
        assert not store.read(thread["thread_id"]).get("archived")
        container.chat.tasks.pop(key)
        assert http.patch(url, json={"archived": True}).status_code == 200
        assert not http.get(base + "?agent_id=anomaly").json()
        assert len(http.get(base + "?agent_id=anomaly&archived=true").json()) == 1
        assert http.get(base + "/" + thread["thread_id"]).json()["archived"]
        assert http.patch(url.replace("/acme/", "/another/"), json={"archived": False}).status_code == 404
        assert (
            http.post(
                base + "/" + thread["thread_id"] + "/messages",
                json={"text": "Continue", "ticket_refs": [], "message_id": uuid4().hex},
            ).status_code
            == 422
        )
        assert http.patch(url, json={"archived": False}).status_code == 200
        assert len(http.get(base + "?agent_id=anomaly").json()) == 1
    finally:
        container.chat.tasks.clear()
        app.dependency_overrides.clear()
