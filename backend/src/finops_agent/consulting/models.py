from datetime import date
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator


class ContextValues(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_accounts: list[str] | None = Field(default=None, max_length=100)
    owners: dict[str, str] | None = None
    objective: str | None = Field(default=None, min_length=1, max_length=1000)
    monthly_budget: FiniteFloat | None = Field(default=None, gt=0)
    source_cadence_days: int | None = Field(default=None, ge=1, le=30)
    data_latency_days: int | None = Field(default=None, ge=0, le=30)
    allocation_target_pct: FiniteFloat | None = Field(default=None, ge=0, le=100)
    minimum_history_days: int | None = Field(default=None, ge=2, le=365)
    known_events: list[str] | None = Field(default=None, max_length=30)
    non_billable_days: dict[str, list[date]] | None = None
    constraints: str | None = Field(default=None, min_length=1, max_length=4000)

    @model_validator(mode='after')
    def meaningful(self) -> 'ContextValues':
        fields = self.model_dump(exclude_none=True)
        if not fields or any(isinstance(v, str) and not v.strip() for v in fields.values()):
            raise ValueError('Completa al menos un dato concreto.')
        if self.expected_accounts is not None and (not self.expected_accounts or any(not x.strip() for x in self.expected_accounts)):
            raise ValueError('Confirma al menos una cuenta válida.')
        if self.owners is not None and any(not k.strip() or not v.strip() for k, v in self.owners.items()):
            raise ValueError('Cada cuenta necesita un responsable válido.')
        return self


class ContextProposal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    values: ContextValues
    reason: str = Field(min_length=1, max_length=2000)


class Decision(BaseModel):
    decision: Literal['confirm', 'reject']
    command_id: str = Field(pattern=r'^[a-f0-9]{32}$')


class Implementation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    command_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    expected_revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    effective_date: date
    evidence: str = Field(min_length=5, max_length=4000)
    baseline_days: int = Field(default=7, ge=2, le=90)
    observation_days: int = Field(default=3, ge=2, le=30)


class ActionDetails(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action_type: Literal['information', 'investigation', 'improvement'] = 'investigation'
    owner: str | None = Field(default=None, min_length=1, max_length=120)
    steps: list[str] = Field(default_factory=list, max_length=15)
    dependencies: list[str] = Field(default_factory=list, max_length=20)
    risk: Literal['LOW', 'MEDIUM', 'HIGH'] | None = None
    approval_required: bool = True
    completion_criterion: str | None = Field(default=None, min_length=1, max_length=2000)
    assessment_id: str | None = None

    @model_validator(mode='after')
    def concrete_steps(self) -> 'ActionDetails':
        if any(not step.strip() or len(step)>2000 for step in self.steps):
            raise ValueError('Cada paso debe ser concreto y tener máximo 2000 caracteres.')
        if len(self.dependencies)!=len(set(self.dependencies)):
            raise ValueError('No repitas dependencias.')
        return self


class CapabilityAssessment(BaseModel):
    key: str
    title: str
    state: Literal['INSUFFICIENT_DATA', 'ASSESSABLE', 'ATTENTION_REQUIRED', 'FOLLOW_UP', 'NO_ISSUES_DETECTED', 'NOT_APPLICABLE']
    reason: str
    phase: Literal['Inform', 'Optimize', 'Operate']
    missing_requirements: list[str]
    ticket_ids: list[str]


class Diagnosis(BaseModel):
    model_config = ConfigDict(extra='allow')
    client_id: str
    revision: str
    evaluated_at: str
    data_through: str | None
    evidence_refs: list[str]
    capabilities: list[CapabilityAssessment]
    requirements: list[dict[str, Any]]
    context: dict[str, Any]


class ConsultingResponse(BaseModel):
    diagnosis: Diagnosis
    agenda: dict[str, Any]
    verifications: list[dict[str, Any]]
