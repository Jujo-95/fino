from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from ..models import TicketStatus, Finding
from .ticket_fields import TicketFields


class Change(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['create','update','transition'] = 'update'
    ticket_id: str | None = Field(default=None,pattern=r'^FIN-\d+$')
    finding: Finding | None = Field(default=None,description='REQUIRED when action=create: full measured Finding object. reason and evidence_refs alone cannot create a ticket. Omit when updating an existing ticket.')
    fields: TicketFields | None = None
    proposal_key: str | None = Field(default=None,max_length=150)
    expected_revision: str | None = Field(default=None,pattern=r'^[a-f0-9]{64}$')
    target_status: TicketStatus | None = None
    append_note: str = Field(default='', max_length=4000)
    reason: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator('evidence_refs',mode='before')
    @classmethod
    def unique_evidence(cls, value: object) -> object:
        if isinstance(value,list) and all(isinstance(item,str) for item in value):
            return list(dict.fromkeys(value))
        return value

    @model_validator(mode='after')
    def meaningful(self) -> 'Change':
        if self.action=='create':
            if self.finding is None or self.ticket_id or self.expected_revision or self.fields or self.target_status:
                raise ValueError('Crear requiere finding; el backend asigna el ID y el estado inicial.')
            return self
        if not self.ticket_id or not self.expected_revision or self.finding:
            raise ValueError('Modificar requiere ticket_id real y expected_revision; consulta el ticket primero.')
        if not self.reason.strip() or (not self.target_status and not self.append_note.strip() and not self.fields):
            raise ValueError('Indica un cambio y su motivo.')
        return self


class PlanRequest(BaseModel):
    changes: list[Change] = Field(min_length=1, max_length=50)

    @model_validator(mode='after')
    def unique(self) -> 'PlanRequest':
        keys = [c.ticket_id if c.action!='create' else tuple(getattr(c.finding,k) for k in
            ('capability','sub_account_id','service_name','kpi_name')) for c in self.changes]
        if len(set(keys)) != len(self.changes):
            raise ValueError('Un ticket solo puede aparecer una vez en el lote.')
        return self


class ChatMessage(BaseModel):
    audit_run_id: str | None = Field(default=None,pattern=r'^[a-f0-9]{32}$')
    text: str = Field(min_length=1, max_length=6000)
    ticket_refs: list[str] = Field(default_factory=list, max_length=50)
    message_id: str = Field(pattern=r'^[a-f0-9]{32}$')

    @model_validator(mode='after')
    def not_blank(self) -> 'ChatMessage':
        if not self.text.strip():
            raise ValueError('Escribe un mensaje.')
        return self


class ResumeRequest(BaseModel):
    decision: Literal['approve', 'reject']
    plan_ids: list[str] = Field(min_length=1, max_length=10)
    message_id: str = Field(pattern=r'^[a-f0-9]{32}$')


class ThreadRequest(BaseModel):
    agent_id: str = Field(default='orchestrator',max_length=100)

    @field_validator('agent_id')
    @classmethod
    def known_agent(cls, value: str) -> str:
        from .agent_context import validate_agent
        return validate_agent(value)
    audit_run_id: str | None = Field(default=None,pattern=r'^[a-f0-9]{32}$')


class ArchiveRequest(BaseModel):
    archived: bool


class TicketThreadRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    parent_thread_id: str | None = Field(default=None,pattern=r'^[a-f0-9]{32}$')
