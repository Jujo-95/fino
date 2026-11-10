import json
from typing import Any


def report_ticket_links(client: Any, run_id: str) -> list[str]:
    with client.engine.lock:
        exists = client.engine.conn.execute("SELECT 1 FROM information_schema.tables WHERE table_name='ticket_commands'").fetchone()
        if not exists:
            return []
        rows = client.engine.conn.execute('SELECT document FROM ticket_commands').fetchall()
    return sorted({t['ticket_id'] for row in rows for receipt in [json.loads(row[0])]
        if receipt.get('report_run_id')==run_id for t in receipt['result']['tickets']})
