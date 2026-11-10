"""Bound report submission retries and reuse a successful receipt within one turn."""
from typing import Any
from ..engine.run_audit import RunAuditStore


class ReportDeliveryError(RuntimeError):
    pass


def saved_receipt(store: Any, thread_id: str) -> dict[str,Any] | None:
    thread = store.read(thread_id)
    key = thread.get('saved_report_run_id')
    if not key or thread.get('saved_report_turn_id')!=thread.get('turn_id'):
        return None
    record = RunAuditStore(store.client.workspace).read(key)
    if record['status']!='completed' or record.get('thread_id')!=thread_id:
        return None
    return dict(evidence_id='run:'+key,run_id=key,status='saved',client_id=store.client.profile.client_id,
        reused=True,message='Este informe ya está guardado. No repitas la operación; comunica su ubicación al usuario.')


def check_submission_failures(store: Any, thread_id: str) -> dict[str,Any]:
    thread = store.read(thread_id)
    errors = [a for a in thread['activity'] if a['tool']=='save_report' and a['turn_id']==thread['turn_id']
        and isinstance(a['result'],dict) and a['result'].get('error')]
    if len(errors)>=2:
        raise ReportDeliveryError('No se pudo validar el informe tras dos intentos. Se detuvo la ejecución para evitar más consumo. '
            'El borrador y los argumentos permanecen en la auditoría; no se ha marcado el informe como completado.')
    return thread
