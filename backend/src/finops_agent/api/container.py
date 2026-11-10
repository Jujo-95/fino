import asyncio
import threading
from dataclasses import dataclass,field
from datetime import date, timedelta
from pathlib import Path
from typing import Any
import yaml
from ..config import KB_DIR, WORKSPACES, atomic_write_text, validate_client
from ..models import ClientProfile
from ..engine.analytics import analyze
from ..engine.duckdb_engine import DuckDBFocusEngine
from ..engine.context_store import ClientContextStore
from ..engine.ticket_manager import AtomicTicketMemoryManager
from ..agents.providers import LLMProviderFactory


@dataclass
class ClientResources:
    workspace: Path
    profile: ClientProfile
    engine: DuckDBFocusEngine
    tickets: AtomicTicketMemoryManager
    query_lock: Any = field(default_factory=threading.RLock)


class AppContainer:
    def __init__(self, workspaces: Path = WORKSPACES, kb_dir: Path = KB_DIR) -> None:
        self.workspaces = workspaces
        self.workspaces.mkdir(parents=True, exist_ok=True)
        self.memory = ClientContextStore(kb_dir)
        from .admission import RequestLimits
        self.request_limits = RequestLimits()
        self.resource_lock = threading.RLock()
        self.clients: dict[str, ClientResources] = {}
        self.llm = LLMProviderFactory.create()
        self.llm_semaphore = asyncio.Semaphore(4)
        self.run_lock = asyncio.Lock()
        from .run_jobs import RunJobs
        self.jobs = RunJobs(self)
        from ..chat.jobs import ChatJobs
        self.chat = ChatJobs(self)

    def client(self, client_id: str) -> ClientResources:
        with self.resource_lock:
            return self._client(client_id)

    def _client(self, client_id: str) -> ClientResources:
        validate_client(client_id)
        if client_id in self.clients:
            return self.clients[client_id]
        workspace = self.workspaces / client_id
        path = workspace / "client_profile.yaml"
        if not path.exists():
            raise KeyError(f"Unknown client: {client_id}")
        profile = ClientProfile.model_validate(yaml.safe_load(path.read_text()))
        (workspace / "storage").mkdir(exist_ok=True)
        engine = DuckDBFocusEngine(workspace / "storage/finops.duckdb")
        tickets = AtomicTicketMemoryManager(workspace, engine, self.memory, client_id)
        self.clients[client_id] = ClientResources(workspace, profile, engine, tickets)
        tickets.index_context("profile", path.read_text())
        for note in (workspace / "context_notes").glob("*.md"):
            tickets.index_context("note:" + note.name, note.read_text())
        return self.clients[client_id]

    def onboard(self, profile: ClientProfile) -> ClientResources:
        workspace = self.workspaces / profile.client_id
        text = yaml.safe_dump(profile.model_dump(mode="json"), sort_keys=False)
        atomic_write_text(workspace / "client_profile.yaml", text)
        if profile.client_id in self.clients:
            self.clients[profile.client_id].profile = profile
        client = self.client(profile.client_id)
        client.tickets.index_context("profile", text)
        return client

    def overview(self, client_id: str, start: str | None = None, end: str | None = None, capture: bool = False) -> dict[str, Any]:
        client = self.client(client_id)
        from ..sources.remote_config import read_remote
        if read_remote(client):
            from ..sources.remote_overview import remote_overview
            return remote_overview(client)
        with client.engine.lock:
            latest_row = client.engine.conn.execute("SELECT max(ChargePeriodStart) FROM focus_usage WHERE client_id=?",
                                               [client_id]).fetchone()
        latest = latest_row[0] if latest_row else None
        last_day = latest.date() if latest else date.today()
        start = start or last_day.replace(day=1).isoformat()
        end = end or (last_day + timedelta(days=1)).isoformat()
        from .routes import validate_period
        validate_period(start, end)
        from ..consulting.store import ConsultingStore
        confirmed = ConsultingStore(client).context()['values'].get('monthly_budget')
        profile = client.profile
        if confirmed:
            profile = profile.model_copy(update={'budget_policy':profile.budget_policy.model_copy(
                update={'total_monthly_budget_usd':confirmed})})
        return dict(analyze(client.engine, profile, start, end, memory=self.memory, capture=capture),
                    budget_confirmed=bool(confirmed))

    def close(self) -> None:
        for client in self.clients.values():
            client.engine.close()
