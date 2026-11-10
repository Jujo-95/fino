"""Reconcile the SQLite commit record with atomic audit projections at startup."""
from typing import Any
from ..engine.run_audit import RunAuditStore


def recover(jobs: Any) -> None:
    for profile in jobs.container.workspaces.glob('*/client_profile.yaml'):
        store = RunAuditStore(profile.parent)
        for summary in store.list(limit=None):
            if summary['status'] not in ('running','queued'):
                continue
            record = store.read(summary['run_id'])
            queued = jobs.analysis.queue.get(summary['run_id'])
            if queued and queued['state']=='queued':
                record.update(status='queued',error='Se retomará desde los resultados durables.')
                store.save(record)
            else:
                store.finish(record,'failed','El backend anterior se detuvo. Los avances se conservaron.')
