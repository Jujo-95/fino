from typing import Any, Literal, TypedDict
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .consulting.models import ActionDetails
from .consulting.followup_models import FollowupPlan

MaturityTier = Literal["Crawl", "Walk", "Run"]
AllocationMode = Literal["Showback", "Chargeback", "N/A"]
TicketStatus = Literal["PROPOSED", "APPROVED", "IMPLEMENTED", "REJECTED", "FALSE_POSITIVE", "SNOOZED", "MONITORING", "RESOLVED"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class AllocationPolicy(FrozenModel):
    mode: Literal["Showback", "Chargeback"] = "Showback"
    required_tags: list[str] = Field(default_factory=lambda: ["owner", "env", "cost_center", "service"])
    shared_cost_sub_accounts: list[str] = Field(default_factory=list)
    shared_apportionment_method: Literal["proportional_effective_cost", "even_split", "fixed_pct"] = "even_split"


class BudgetPolicy(FrozenModel):
    cycle: Literal["monthly"] = "monthly"
    total_monthly_budget_usd: float = Field(default=120000, gt=0)
    holdback_pct: float = Field(default=10, ge=0, le=100)
    sub_account_budgets_usd: dict[str, float] = Field(default_factory=dict)


class CommitmentPolicy(FrozenModel):
    max_term_months: int = Field(default=12, ge=1, le=36)
    allow_upfront_payment: bool = False
    target_esr_pct: float = Field(default=22, ge=0, le=100)


class MaterialityThreshold(FrozenModel):
    absolute: float = Field(default=1, ge=0)
    relative_pct: float = Field(default=5, ge=0)


class IncrementalPolicy(FrozenModel):
    default: MaterialityThreshold = Field(default_factory=MaterialityThreshold)
    metrics: dict[str, MaterialityThreshold] = Field(default_factory=dict)


class ClientProfile(FrozenModel):
    incremental_policy: IncrementalPolicy = Field(default_factory=IncrementalPolicy)
    client_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    client_name: str = Field(min_length=1, max_length=120)
    niche: str = "Cloud services"
    billing_currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    timezone: Literal["UTC"] = "UTC"
    target_maturity: MaturityTier = "Walk"
    allocation_policy: AllocationPolicy = Field(default_factory=AllocationPolicy)
    budget_policy: BudgetPolicy = Field(default_factory=BudgetPolicy)
    commitment_policy: CommitmentPolicy = Field(default_factory=CommitmentPolicy)
    previous_forecast_spend: float | None = None
    forecasted_usage_quantity: float | None = None
    planned_monthly_cost: float = 0

    @model_validator(mode="after")
    def usd_budget(self) -> "ClientProfile":
        if self.billing_currency != "USD":
            raise ValueError("This version requires USD budgets; mixed currency analysis is blocked.")
        return self


class Finding(FrozenModel):
    ticket_kind: Literal["finding", "onboarding", "analysis", "verification"] = "finding"
    workflow_key: str | None = None
    action_details: ActionDetails = Field(default_factory=ActionDetails)
    capability: str
    maturity_tier: MaturityTier
    allocation_mode: AllocationMode
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    sub_account_id: str
    service_name: str
    period_bucket: str
    kpi_name: str
    kpi_value: float | None
    estimated_monthly_impact_usd: float | None
    title: str
    evidence_summary: str
    recommended_action: str
    capability_citation_url: str

    @model_validator(mode="after")
    def task_evidence(self) -> "Finding":
        if self.ticket_kind == "finding" and self.kpi_value is None:
            raise ValueError("Un hallazgo requiere un indicador medido.")
        if self.ticket_kind != "finding" and (not self.workflow_key or self.estimated_monthly_impact_usd is not None):
            raise ValueError("Una tarea requiere identidad estable y no puede atribuirse ahorro.")
        return self


class TicketContributor(FrozenModel):
    agent_id: str
    role: Literal["detected", "consolidated"]
    run_id: str


class FinOpsTicket(Finding):
    snoozed_until: date | None = None
    first_detected_at: str | None = None
    last_evaluated_at: str | None = None
    last_changed_analysis_id: str | None = None
    is_new: bool = False
    reviewed_at_utc: str | None = None
    needs_attention: bool = False
    attention_reason: str = ''
    last_evaluated_run_id: str | None = None
    followup: FollowupPlan | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)
    note_history: list[dict[str, str]] = Field(default_factory=list)
    contributors: list[TicketContributor] = Field(default_factory=list)
    fingerprint: str
    ticket_id: str
    client_id: str
    status: TicketStatus = "PROPOSED"
    resolution_note: str = ""
    billing_currency: str = "USD"
    created_at_utc: str
    updated_at_utc: str


class RunRequest(FrozenModel):
    analysis_only: bool = False
    scheduled: bool = False
    repeat_confirmation: str | None = Field(default=None,pattern=r'^[a-f0-9]{64}$')
    force_reanalysis: bool = False
    force_reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def require_force_reason(self) -> "RunRequest":
        if self.force_reanalysis and not self.force_reason.strip():
            raise ValueError("A forced reanalysis requires a reason")
        return self

    client_id: str
    run_mode: Literal["onboarding", "daily"] = "daily"
    period_start_utc: str
    period_end_utc: str
    billing_currency: Literal["USD"] = "USD"
    instruction: str = Field(default="", max_length=4000)
    reference_run_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class TicketUpdate(FrozenModel):
    snoozed_until: date | None = None
    status: TicketStatus
    resolution_note: str = Field(min_length=1, max_length=4000)


class FinOpsGraphState(TypedDict, total=False):
    force_reanalysis: bool
    force_reason: str
    input_signature: dict[str, str]
    ticket_inputs: list[dict[str, str]]
    baseline: dict[str, Any] | None
    reuse_report: bool
    reused_run_id: str
    historical_context: dict[str, Any]
    incremental: dict[str, Any]
    report_file: str

    run_id: str
    instruction: str
    reference_run_id: str | None
    reference_report: str
    audit_traces: list[dict[str, Any]]
    client_id: str
    run_mode: str
    period_start_utc: str
    period_end_utc: str
    billing_currency: str
    ingested_rows: int
    kpi_snapshots: dict[str, Any]
    active_anomalies: list[str]
    excluded_baseload: list[str]
    findings: list[dict[str, Any]]
    emitted_tickets: list[str]
    specialist_commentary: dict[str, str]
    report_markdown: str
