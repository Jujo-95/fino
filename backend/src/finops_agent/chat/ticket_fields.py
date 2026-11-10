from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator
from datetime import date
from ..consulting.models import ActionDetails
from ..consulting.followup_models import FollowupPlan


class TicketFields(BaseModel):
    model_config = ConfigDict(extra='forbid')
    snoozed_until: date | None = None
    followup: FollowupPlan | None = None
    tags: list[str] | None = Field(default=None, max_length=20)
    action_details: ActionDetails | None = None
    title: str | None = Field(default=None,min_length=1,max_length=300)
    severity: str | None = Field(default=None,pattern='^(LOW|MEDIUM|HIGH|CRITICAL)$')
    recommended_action: str | None = Field(default=None,min_length=1,max_length=6000)
    evidence_summary: str | None = Field(default=None,min_length=1,max_length=6000)
    estimated_monthly_impact_usd: FiniteFloat | None = Field(default=None,ge=0)
    kpi_value: FiniteFloat | None = None

    @model_validator(mode='after')
    def valid_fields(self) -> 'TicketFields':
        fields = self.model_dump(exclude_unset=True)
        if not fields or any(v is None for k,v in fields.items() if k!='estimated_monthly_impact_usd'):
            raise ValueError('Indica campos válidos; no pueden quedar vacíos.')
        if self.tags is not None and (len(set(self.tags))!=len(self.tags) or any(not t.strip() or len(t)>60 for t in self.tags)):
            raise ValueError('Usa etiquetas únicas, no vacías y de máximo 60 caracteres.')
        if any(isinstance(v,str) and not v.strip() for v in fields.values()):
            raise ValueError('Los campos de texto no pueden quedar vacíos.')
        return self
