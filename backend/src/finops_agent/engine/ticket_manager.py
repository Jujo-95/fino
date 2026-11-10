import builtins
from typing import Any
from datetime import datetime, timezone
from pathlib import Path
import yaml
from ..config import atomic_write_text, make_fingerprint
from ..models import Finding, FinOpsTicket, TicketUpdate, TicketContributor
from ..consulting.followup_models import FollowupPlan
from .duckdb_engine import DuckDBFocusEngine
from .context_store import ClientContextStore
from .schema import LEDGER_FIELDS


def ticket_markdown(ticket: FinOpsTicket) -> str:
    metric = f"**{ticket.kpi_name}**: {ticket.kpi_value:,.2f}" if ticket.kpi_value is not None else "Tarea sin indicador medido."
    metadata = yaml.safe_dump(ticket.model_dump(mode="json"), sort_keys=False)
    return (f"---\n{metadata}---\n# {ticket.title}\n\n## Evidence & KPI Formula\n"
            f"{ticket.evidence_summary}\n\n{metric}\n\n"
            f"{ticket.billing_currency} · UTC · {ticket.maturity_tier} · {ticket.allocation_mode}\n\n"
            f"## FinOps Foundation Guidance\n{ticket.capability_citation_url}\n\n"
            f"## Recommended Action\n{ticket.recommended_action}\n\n"
            f"## Verification Plan\n{verification_text(ticket)}\n\n"
            f"## Resolution / Client Feedback\n{ticket.resolution_note or 'Pending review.'}\n")


def verification_text(ticket: FinOpsTicket) -> str:
    plan = ticket.followup
    if not plan:
        return 'No aplica: es una tarea de contexto o diagnóstico.'
    start, end = plan.window()
    return (f"{plan.check}; ventana {start} → {end} (fin exclusivo); "
            f"criterio: {plan.closure_criterion}")


class AtomicTicketMemoryManager:
    def __init__(self, workspace: Path, engine: DuckDBFocusEngine, memory: ClientContextStore,
                 client_id: str) -> None:
        self.workspace, self.db, self.memory, self.client_id = workspace, engine, memory, client_id
        self.recover()

    def recover(self) -> None:
        # DuckDB is the durable commit record. Repair file projections after an interrupted process.
        for ticket in self.list():
            atomic_write_text(self.workspace / "tickets" / f"{ticket.ticket_id}.md", ticket_markdown(ticket))
        self.memory.restore(self.client_id, self.db)

    def list(self, status: str | None = None, capability: str | None = None) -> list[FinOpsTicket]:
        with self.db.lock:
            rows = self.db.conn.execute("SELECT document FROM tickets_ledger WHERE client_id=? ORDER BY ticket_id",
                                        [self.client_id]).fetchall()
        tickets = [FinOpsTicket.model_validate_json(row[0]) for row in rows]
        from ..consulting.ticket_lifecycle import matches_status
        return [t for t in tickets if matches_status(t.model_dump(mode='json'),status) and (not capability or t.capability == capability)]

    def create(self, finding: Finding, contributors: builtins.list[TicketContributor] | None = None) -> FinOpsTicket:
        key = make_fingerprint(self.client_id, finding.capability, finding.sub_account_id,
                               finding.service_name, finding.period_bucket, finding.kpi_name)
        with self.db.lock:
            legacy = make_fingerprint(self.client_id, finding.capability, finding.sub_account_id,
                                      finding.service_name, finding.period_bucket)
            existing = self.db.conn.execute("SELECT document FROM tickets_ledger WHERE fingerprint=? "
                "OR (fingerprint=? AND kpi_name=?)", [key, legacy, finding.kpi_name]).fetchone()
            existing = existing or self._continuing(finding)
            if existing:
                old = FinOpsTicket.model_validate_json(existing[0])
                return self._refresh_proposal(old, finding, contributors or [])
            return self._commit(self.prepare_create(finding,contributors or []))

    def find_existing(self, finding: Finding) -> FinOpsTicket | None:
        key = make_fingerprint(self.client_id,finding.capability,finding.sub_account_id,
            finding.service_name,finding.period_bucket,finding.kpi_name)
        row = self.db.conn.execute('SELECT document FROM tickets_ledger WHERE fingerprint=?',[key]).fetchone()
        row = row or self._continuing(finding)
        return FinOpsTicket.model_validate_json(row[0]) if row else None

    def prepare_create(self, finding: Finding, contributors: builtins.list[TicketContributor], offset: int = 0) -> FinOpsTicket:
        existing = self.find_existing(finding)
        if existing:
            raise ValueError(f'Ya existe {existing.ticket_id} para este hallazgo; propón actualizarlo.')
        row = self.db.conn.execute("SELECT coalesce(max(try_cast(substr(ticket_id,5) AS INTEGER)),0) FROM tickets_ledger").fetchone()
        number = (row[0] if row else 0)+1+offset
        now = datetime.now(timezone.utc).isoformat()
        key = make_fingerprint(self.client_id,finding.capability,finding.sub_account_id,
            finding.service_name,finding.period_bucket,finding.kpi_name)
        followup: FollowupPlan | None = None
        if finding.ticket_kind == 'finding':
            from ..consulting.verification_plan import default_plan
            followup = default_plan(finding)
        return FinOpsTicket(**finding.model_dump(),followup=followup,fingerprint=key,ticket_id=f'FIN-{number:03d}',
            contributors=contributors,is_new=True,first_detected_at=now,needs_attention=True,attention_reason='Requiere revisión inicial.',
            client_id=self.client_id,billing_currency='USD',created_at_utc=now,updated_at_utc=now)

    def _continuing(self, finding: Finding) -> tuple[str] | None:
        row = self.db.conn.execute("SELECT document FROM tickets_ledger WHERE client_id=? AND capability=? "
            "AND sub_account_id=? AND service_name=? AND kpi_name=? ORDER BY updated_at_utc DESC LIMIT 1",
            [self.client_id, finding.capability, finding.sub_account_id, finding.service_name, finding.kpi_name]).fetchone()
        return (str(row[0]),) if row else None

    def _refresh_proposal(self, old: FinOpsTicket, finding: Finding, contributors: builtins.list[TicketContributor]) -> FinOpsTicket:
        merged = list(old.contributors)
        merged.extend(item for item in contributors if item not in merged)
        if old.status != "PROPOSED":
            return self._commit(old.model_copy(update={"contributors": merged})) if merged != old.contributors else old
        update = {**finding.model_dump(), "contributors": merged, "updated_at_utc": datetime.now(timezone.utc).isoformat()}
        if not finding.action_details.model_fields_set:
            update['action_details'] = old.action_details.model_dump()
        if old.followup is None and finding.ticket_kind == 'finding':
            from ..consulting.verification_plan import default_plan
            update['followup'] = default_plan(finding)
        return self._commit(FinOpsTicket.model_validate({**old.model_dump(), **update}))

    def update(self, ticket_id: str, update: TicketUpdate) -> FinOpsTicket:
        with self.db.lock:
            old = next((t for t in self.list() if t.ticket_id == ticket_id), None)
            if old is None:
                raise KeyError(ticket_id)
            ticket = old.model_copy(update={**update.model_dump(), 'needs_attention':update.status in ('PROPOSED','APPROVED'),
                'attention_reason':'Requiere una decisión o acción.' if update.status in ('PROPOSED','APPROVED') else '',
                "updated_at_utc": datetime.now(timezone.utc).isoformat()})
            return self._commit(ticket)

    def _commit(self, ticket: FinOpsTicket) -> FinOpsTicket:
        path = self.workspace / "tickets" / f"{ticket.ticket_id}.md"
        before = path.read_text() if path.exists() else None
        text = ticket_markdown(ticket)
        graph = self.memory.prepared_graph(self.client_id, ticket.fingerprint, text)
        try:
            self._persist(ticket, path, text)
        except BaseException:
            self._restore_file(path, before)
            raise
        self.memory.clients[self.client_id] = graph
        return ticket

    def _persist(self, ticket: FinOpsTicket, path: Path, text: str) -> None:
        with self.db.atomic_tx() as tx:
            self._write_ticket(tx, ticket, path, text)

    def _write_ticket(self, tx: Any, ticket: FinOpsTicket, path: Path, text: str) -> None:
        from ..consulting.progress_history import record_transition
        record_transition(tx,ticket)
        columns = ["fingerprint", "ticket_id", "client_id", "capability", "status", "document", *LEDGER_FIELDS]
        values = ticket.model_dump()
        values["document"] = ticket.model_dump_json()
        placeholders = ",".join("?" for _ in columns)
        updates = ",".join(f"{name}=excluded.{name}" for name in columns if name != "fingerprint")
        tx.execute(f"INSERT INTO tickets_ledger ({','.join(columns)}) VALUES ({placeholders}) "
                   f"ON CONFLICT(fingerprint) DO UPDATE SET {updates}", [values[key] for key in columns])
        tx.execute("INSERT OR REPLACE INTO context_documents VALUES (?,?)", [ticket.fingerprint, text])
        atomic_write_text(path, text)

    def _restore_file(self, path: Path, before: str | None) -> None:
        if before is None:
            path.unlink(missing_ok=True)
        else:
            atomic_write_text(path, before)

    def index_context(self, doc_id: str, text: str) -> None:
        with self.db.lock:
            graph = self.memory.prepared_graph(self.client_id, doc_id, text)
            with self.db.atomic_tx() as tx:
                tx.execute("INSERT OR REPLACE INTO context_documents VALUES (?,?)", [doc_id, text])
            self.memory.clients[self.client_id] = graph
