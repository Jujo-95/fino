"""Bind context CAS to the server's actual read, not a model-selected ticket hash."""
from typing import Any


def proposal_revision(ctx: Any, supplied: str | None) -> str:
    thread = ctx.store.read(ctx.thread_id)
    reads = [a['result'] for a in thread['activity']
        if a['tool']=='read_confirmed_context' and a['turn_id']==ctx.turn_id]
    for result in reversed(reads):
        bound = result.get('confirmed_context',{}).get('revision') or result.get('revision')
        if bound and result.get('client_id')==ctx.client.profile.client_id:
            return str(bound)
    # Legacy callers retain strict optimistic concurrency; never infer a fresh revision.
    if supplied:
        return supplied
    raise ValueError('Primero consulta el contexto confirmado; no se pudo vincular una revisión del cliente.')
