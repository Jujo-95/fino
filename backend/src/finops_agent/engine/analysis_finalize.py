"""Reuse the existing native onboarding workflow after retaining measured inputs."""
from typing import Any
from .analysis_store import save_analysis


def finalize(client: Any, result: dict[str,Any], create_tasks: bool) -> None:
    save_analysis(client,result)
    if create_tasks:
        from ..consulting.workflow import sync_tasks
        before = {t.ticket_id for t in client.tickets.list()}
        sync_tasks(client)
        result['actions'].extend(dict(ticket_id=t.ticket_id,action='created',kind=t.ticket_kind)
            for t in client.tickets.list() if t.ticket_id not in before)
    from .analysis_service import analysis_key
    from ..consulting.store import ConsultingStore
    result['analysis_key'] = analysis_key(client,result['source_revision'],ConsultingStore(client).context())
    save_analysis(client,result)
