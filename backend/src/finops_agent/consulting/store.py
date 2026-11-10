import json
from typing import Any
from ..agents.audit_trace import timestamp
from ..engine.incremental_inputs import digest
from .models import ContextProposal


class ConsultingStore:
    def __init__(self, client: Any) -> None:
        self.client = client
        with client.engine.atomic_tx() as tx:
            tx.execute('CREATE TABLE IF NOT EXISTS consulting_records '
                       '(kind VARCHAR, id VARCHAR, document JSON, PRIMARY KEY(kind,id))')

    def get(self, kind: str, key: str) -> dict[str, Any] | None:
        with self.client.engine.lock:
            row = self.client.engine.conn.execute('SELECT document FROM consulting_records WHERE kind=? AND id=?', [kind, key]).fetchone()
        return dict(json.loads(row[0])) if row else None

    def all(self, kind: str) -> list[dict[str, Any]]:
        with self.client.engine.lock:
            rows = self.client.engine.conn.execute('SELECT document FROM consulting_records WHERE kind=? ORDER BY id', [kind]).fetchall()
        return [json.loads(row[0]) for row in rows]

    def put(self, tx: Any, kind: str, key: str, document: dict[str, Any]) -> None:
        tx.execute('INSERT OR REPLACE INTO consulting_records VALUES (?,?,?)', [kind, key, json.dumps(document, default=str)])

    def context(self) -> dict[str, Any]:
        current = self.get('context', 'current') or dict(values={}, history=[])
        return dict(client_id=self.client.profile.client_id, **current, revision=digest(current))

    def propose(self, body: ContextProposal, source: str) -> dict[str, Any]:
        with self.client.engine.atomic_tx() as tx:
            if body.expected_revision != self.context()['revision']:
                raise ValueError('El contexto cambió; vuelve a consultarlo.')
            key = digest([source, body.model_dump(mode='json')])
            existing = self.get('context_proposal', key)
            if existing:
                return existing
            proposal = dict(proposal_id=key, client_id=self.client.profile.client_id, source=source,
                            status='pending', created_at=timestamp(), **body.model_dump(mode='json', exclude_none=True))
            self.put(tx, 'context_proposal', key, proposal)
        return proposal

    def decide(self, key: str, decision: str, command_id: str) -> dict[str, Any]:
        with self.client.engine.atomic_tx() as tx:
            proposal = self.get('context_proposal', key)
            if not proposal:
                raise KeyError('Propuesta no encontrada para este cliente.')
            receipt = self.get('context_command', command_id)
            if receipt:
                if receipt['proposal_id'] != key or receipt['decision'] != decision:
                    raise ValueError('El comando ya pertenece a otra decisión.')
                return receipt
            if proposal['status'] != 'pending':
                if proposal['status'] == ('confirmed' if decision == 'confirm' else 'rejected'):
                    return proposal
                raise ValueError('Esta propuesta ya fue resuelta.')
            return self._commit_decision(tx, proposal, decision, command_id)

    def _commit_decision(self, tx: Any, proposal: dict[str, Any], decision: str, command_id: str) -> dict[str, Any]:
        current = self.context()
        if decision == 'confirm' and current['revision'] != proposal['expected_revision']:
            raise ValueError('La propuesta está desactualizada; vuelve a preparar el cambio.')
        now = timestamp()
        if decision == 'confirm':
            history = [*current['history'], dict(at=now, actor='local-user', source=proposal['source'],
                       reason=proposal['reason'], previous=current['values'], values=proposal['values'])]
            values = {**current['values'], **proposal['values']}
            self.put(tx, 'context', 'current', dict(values=values, history=history, confirmed_at=now))
            tx.execute('INSERT OR REPLACE INTO context_documents VALUES (?,?)',
                       ['consulting:confirmed', json.dumps(dict(values=values, confirmed_at=now))])
        proposal.update(status='confirmed' if decision == 'confirm' else 'rejected', decided_at=now)
        self.put(tx, 'context_proposal', proposal['proposal_id'], proposal)
        result = dict(proposal_id=proposal['proposal_id'], decision=decision, status=proposal['status'])
        self.put(tx, 'context_command', command_id, result)
        return result
