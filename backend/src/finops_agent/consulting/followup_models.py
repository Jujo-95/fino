from datetime import date, timedelta
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class FollowupPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=5, max_length=2000)
    event_date: date
    observation_days: int = Field(default=3, ge=2, le=90)
    baseline_days: int = Field(default=7, ge=2, le=90)
    check: Literal['return_to_baseline', 'specialist_review'] = 'specialist_review'
    tolerance_pct: float = Field(default=20, ge=0, le=100, allow_inf_nan=False)
    closure_criterion: str = Field(min_length=10, max_length=2000)

    @model_validator(mode='after')
    def concrete(self) -> 'FollowupPlan':
        if not self.reason.strip() or not self.closure_criterion.strip():
            raise ValueError('Explica el motivo y el criterio verificable de cierre.')
        if self.event_date > date.today():
            raise ValueError('La fecha del evento no puede ser futura.')
        return self

    def window(self) -> tuple[date, date]:
        start = self.event_date+timedelta(days=1)
        return start, start+timedelta(days=self.observation_days)
