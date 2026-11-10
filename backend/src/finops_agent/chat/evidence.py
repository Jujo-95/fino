from typing import Any, cast
from ..models import FinOpsGraphState
from ..agents.query_tools import AgentTools
from ..agents.specs import SPECIALIST_SPECS
from ..agents.runner import SpecialistRunner
from ..engine.script_store import ScriptStore
from ..engine.run_audit import RunAuditStore
from ..engine.incremental_inputs import prior_context
from ..config import KB_DIR


class ChatEvidence:
    def __init__(self, container: Any, client_id: str, agent_id: str = 'orchestrator') -> None:
        self.container, self.client_id = container, client_id
        self.agent_id = agent_id
        self.tools: AgentTools | None = None
        self.refinements = 0

    def current(self) -> AgentTools:
        if self.tools is None:
            overview = self.container.overview(self.client_id, capture=True)
            client = self.container.client(self.client_id)
            overview['snapshot_id'] = ScriptStore(client.engine).save(overview, 'chat')
            self.tools = AgentTools(self.container, dict(client_id=self.client_id,
                period_start_utc=overview['period_start_utc'], period_end_utc=overview['period_end_utc'],
                billing_currency=client.profile.billing_currency, kpi_snapshots=overview,
                findings=[], audit_traces=[]), 'chat_'+self.agent_id)
        return self.tools

    def report(self, run_id: str | None) -> dict[str, Any]:
        store = RunAuditStore(self.container.client(self.client_id).workspace)
        if not run_id:
            run_id = next((row['run_id'] for row in store.list() if row['status']=='completed'), None)
        if not run_id:
            return dict(available=False, message='Todavía no hay un informe completado.')
        record = store.detail(run_id)
        if record.get('client_id')!=self.client_id:
            raise ValueError('El informe no corresponde al cliente activo.')
        if record['status'] != 'completed':
            raise ValueError('El informe todavía no está completado.')
        from .report_ticket_links import report_ticket_links
        return dict(ticket_ids=report_ticket_links(self.container.client(self.client_id),run_id),evidence_id='run:'+run_id, run_id=run_id, created_at=record['finished_at_utc'],
            incremental=record.get('incremental'), structured_report=record.get('structured_report'), report=record['report_markdown'][:16000],
            truncated=len(record['report_markdown'])>16000)

    def guidance(self, capability: str) -> dict[str, Any]:
        if capability not in {spec.capability_slug for spec in SPECIALIST_SPECS.values()}:
            raise ValueError('Selecciona una capacidad del equipo de análisis.')
        return dict(evidence_id='guidance:'+capability, text=(KB_DIR/(capability+'.md')).read_text()[:16000])

    async def specialist(self, specialist: str, question: str) -> dict[str, Any]:
        if specialist not in SPECIALIST_SPECS or self.refinements >= 1:
            raise ValueError('Máximo una consulta especializada por mensaje; elige un especialista válido.')
        self.refinements += 1
        state = {**self.current().state, 'instruction':question, 'refinement':question}
        client = self.container.client(self.client_id)
        previous = self.report(None)
        record = RunAuditStore(client.workspace).detail(previous['run_id']) if previous.get('available') is not False else None
        state['historical_context'] = prior_context(record,client.tickets.list())
        result = await SpecialistRunner(SPECIALIST_SPECS[specialist], self.container)(cast(FinOpsGraphState,state))
        trace = result['audit_traces'][-1]
        return dict(evidence_id='specialist:'+specialist, findings=trace['findings'],
                    summary=trace.get('llm_output'), queries=trace['queries'], metrics=trace['metrics'])
