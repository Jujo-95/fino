"""Versioned structured output shared by jobs, chat and retained evidence."""
from typing import Any,Literal
from pydantic import BaseModel,ConfigDict,Field


class AnalysisRun(BaseModel):
    model_config = ConfigDict(extra='allow')
    schema_version: Literal[1] = 1
    analysis_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    client_id: str
    trigger: Literal['manual','schedule','chat']
    status: Literal['queued','running','completed','partial','failed','cancelled','skipped']
    analysis_key: str
    source_revision: str
    policy_revision: str
    context_revision: Any
    query_catalog_version: str
    period: dict[str,str]
    measurements: list[dict[str,Any]]
    findings: list[dict[str,Any]]
    actions: list[dict[str,Any]]
    coverage: list[dict[str,Any]]
    limitations: list[str]
