"""One durable transaction for a batch, its context projections and its command receipt."""
import json
from typing import Any
from ..models import FinOpsTicket
from .ticket_manager import ticket_markdown


def commit_batch(manager: Any, tickets: list[FinOpsTicket], receipt: dict[str, Any]) -> dict[str, Any]:
    paths = {t.ticket_id:manager.workspace/'tickets'/f'{t.ticket_id}.md' for t in tickets}
    before = {key:path.read_text() if path.exists() else None for key,path in paths.items()}
    graph = dict(manager.memory.clients.get(manager.client_id, {}))
    result = dict(command_id=receipt['command_id'], plan_id=receipt['plan_id'], status='applied',
                  tickets=[t.model_dump(mode='json') for t in tickets],report_run_id=receipt.get('report_run_id'))
    try:
        with manager.db.atomic_tx() as tx:
            for ticket in tickets:
                text = ticket_markdown(ticket)
                manager._write_ticket(tx, ticket, paths[ticket.ticket_id], text)
                graph[ticket.fingerprint] = text
            tx.execute('INSERT INTO ticket_commands VALUES (?,?,?,?)', [receipt['command_id'],
                receipt['plan_id'], receipt['thread_id'], json.dumps({**receipt, 'result':result})])
            tx.execute("UPDATE ticket_change_plans SET status='applied' WHERE plan_id=?", [receipt['plan_id']])
    except BaseException:
        for key,path in paths.items():
            manager._restore_file(path, before[key])
        raise
    manager.memory.clients[manager.client_id] = graph
    return result
