from typing import Any
from sqlglot import exp
from ..agents_v2.registry import use_cases
from ..agents_v2.reference_sql import reference_tree
from ..engine.schema import COLUMNS


def use_case_availability(client: Any) -> list[dict[str, Any]]:
    # Static/data completeness preflight, not a claim that reference SQL executed successfully.
    fields = ','.join(f'count("{name}")' for name in COLUMNS)
    with client.engine.lock:
        counts = client.engine.conn.execute(f'SELECT {fields} FROM focus_usage WHERE client_id=? AND BillingCurrency=?',
            [client.profile.client_id, client.profile.billing_currency]).fetchone()
    available = {name.lower() for name,count in zip(COLUMNS, counts or []) if count}
    from ..sources.remote_config import read_remote
    if read_remote(client):
        import json
        path = client.workspace/'remote-schema.json'
        available = {name.lower() for name in json.loads(path.read_text())['columns']} if path.exists() else set()
    result = []
    for key, case in use_cases().items():
        try:
            tree = reference_tree(case['sql'][0])
            aliases = {alias.alias.lower() for alias in tree.find_all(exp.Alias)}
            columns = {c.name for c in tree.find_all(exp.Column) if c.name.lower() not in aliases}
            missing = sorted(name for name in columns if name.lower() not in available)
            result.append(dict(use_case_id=key, title=case['title'], missing_fields=missing,
                status='needs_input' if missing else 'preflight_ready'))
        except Exception:
            result.append(dict(use_case_id=key, title=case['title'], status='requires_query_validation'))
    return result
