"""Conservative direct-order recognition. Model-generated approval flags are never trusted."""
import re
from typing import Any

STATES = {'falsos positivos':'FALSE_POSITIVE', 'falso positivo':'FALSE_POSITIVE',
    'implementados':'IMPLEMENTED', 'implementado':'IMPLEMENTED', 'aprobados':'APPROVED',
    'aprobado':'APPROVED', 'rechazados':'REJECTED', 'rechazado':'REJECTED',
    'pospuestos':'SNOOZED', 'pospuesto':'SNOOZED', 'propuestos':'PROPOSED', 'propuesto':'PROPOSED'}


def explicit_order(text: str) -> dict[str, Any]:
    pattern = r'^(?:por favor[, ]+)?(?:mueve|pasa|marca|cambia)\s+(.+?)\s+a\s+('+ '|'.join(STATES)+r')\s+(?:porque\s+|(?:motivo|nota):\s*)(.+)$'
    match = re.fullmatch(pattern, text.strip(), flags=re.I|re.S)
    if match:
        ids = re.findall(r'#?(FIN-\d+)', match[1], flags=re.I)
        remainder = re.sub(r'#?FIN-\d+|\by\b|[\s,]', '', match[1], flags=re.I)
        if ids and not remainder and len(ids) == len(set(ids)):
            return dict(ticket_ids=[key.upper() for key in ids], target_status=STATES[match[2].lower()], note=match[3].strip())
    match = re.fullmatch(r'(?:añade|agrega)\s+(?:esta\s+)?nota\s+a\s+(.+?):\s*(.+)', text.strip(), flags=re.I|re.S)
    if match:
        ids = re.findall(r'#?(FIN-\d+)', match[1], flags=re.I)
        remainder = re.sub(r'#?FIN-\d+|\by\b|[\s,]', '', match[1], flags=re.I)
        if ids and not remainder and len(ids) == len(set(ids)):
            return dict(ticket_ids=[key.upper() for key in ids], target_status=None, note=match[2].strip())
    return {}


def authorized_directly(plan: dict[str, Any], thread: dict[str, Any]) -> bool:
    order = thread.get('direct_order', {})
    return bool(order and all(c.get('action','update')!='create' and not c.get('fields') for c in plan['changes']) and set(order['ticket_ids']) == {c['ticket_id'] for c in plan['changes']}
        and all(c['target_status'] == order['target_status'] and c['append_note'].strip() == order['note']
                for c in plan['changes']))
