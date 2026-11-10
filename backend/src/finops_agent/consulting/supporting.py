from datetime import date
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator
from ..engine.incremental_inputs import digest
from ..agents.audit_trace import timestamp
from .store import ConsultingStore


class UtilizationRow(BaseModel):
    model_config = ConfigDict(extra='forbid')
    account: str = Field(min_length=1, max_length=200)
    resource_id: str = Field(min_length=1, max_length=300)
    day: date
    cpu_pct: FiniteFloat = Field(ge=0, le=100)
    memory_pct: FiniteFloat = Field(ge=0, le=100)


class CommitmentTerm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    account: str = Field(min_length=1, max_length=200)
    commitment_id: str = Field(min_length=1, max_length=300)
    starts_at: date
    expires_at: date
    committed_amount_usd: FiniteFloat = Field(gt=0)

    @model_validator(mode='after')
    def ordered(self) -> 'CommitmentTerm':
        if self.expires_at <= self.starts_at:
            raise ValueError('El vencimiento debe ser posterior al inicio.')
        return self


class SupportingInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: str = Field(min_length=3, max_length=300)
    evidence_reference: str = Field(min_length=3, max_length=1000)
    utilization: list[UtilizationRow] = Field(default_factory=list, max_length=1000)
    commitments: list[CommitmentTerm] = Field(default_factory=list, max_length=200)

    @model_validator(mode='after')
    def nonempty(self) -> 'SupportingInput':
        if not self.utilization and not self.commitments:
            raise ValueError('Incluye observaciones o términos de compromisos.')
        return self


def import_supporting(client: Any, body: SupportingInput) -> dict[str, Any]:
    store = ConsultingStore(client)
    batch = digest(body.model_dump(mode='json'))
    with client.engine.atomic_tx() as tx:
        existing = store.get('supporting_import', batch)
        if existing:
            return existing
        for kind, rows in (('utilization', body.utilization), ('commitment', body.commitments)):
            for row in rows:
                identity = [row.account, row.resource_id, row.day] if isinstance(row, UtilizationRow) else [row.account, row.commitment_id]
                document = dict(**row.model_dump(mode='json'), source=body.source,
                    evidence_reference=body.evidence_reference, imported_at=timestamp())
                store.put(tx, kind, digest(identity), document)
        result = dict(client_id=client.profile.client_id, utilization=len(body.utilization), commitments=len(body.commitments))
        store.put(tx, 'supporting_import', batch, result)
    return result


def supporting_data(client: Any) -> dict[str, Any]:
    store = ConsultingStore(client)
    utilization, commitments = store.all('utilization'), store.all('commitment')
    return dict(client_id=client.profile.client_id, evidence_id='supporting:'+digest([utilization, commitments]),
        utilization=utilization[:100], commitments=commitments[:100],
        utilization_count=len(utilization), commitment_count=len(commitments),
        truncated=len(utilization)>100 or len(commitments)>100,
        latest_utilization_day=max((r['day'] for r in utilization),default=None))


def supporting_quality(client: Any, facts: dict[str, Any], minimum_days: int) -> dict[str, Any]:
    store = ConsultingStore(client)
    with client.engine.lock:
        resources = set(client.engine.conn.execute('SELECT DISTINCT SubAccountId,ResourceId FROM focus_usage WHERE client_id=?',
                                                   [client.profile.client_id]).fetchall())
        commitments = set(client.engine.conn.execute('SELECT DISTINCT SubAccountId,CommitmentDiscountId FROM focus_usage WHERE client_id=?',
                                                     [client.profile.client_id]).fetchall())
    observations = [r for r in store.all('utilization') if (r['account'], r['resource_id']) in resources
                    and facts['available_from'] <= r['day'] <= facts['data_through']]
    days = {r['day'] for r in observations}
    terms = [r for r in store.all('commitment') if (r['account'], r['commitment_id']) in commitments
             and r['starts_at'] <= facts['data_through'] < r['expires_at']]
    return dict(utilization_ready=len(days)>=minimum_days, matched_utilization_days=len(days),
                matched_active_terms=len(terms), method='Matched to billed identities and available billing window; still requires specialist validation.')
