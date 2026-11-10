"""Bounded specialist deliverables; intermediate monologues are not report inputs."""
import json
from typing import Any
from pydantic import BaseModel,ConfigDict,Field


class Contribution(BaseModel):
    model_config = ConfigDict(extra='ignore')
    summary: str = Field(max_length=3000)
    findings: list[dict[str,Any]] = Field(default_factory=list,max_length=30)
    limitations: list[str] = Field(default_factory=list,max_length=20)
    evidence_refs: list[str] = Field(default_factory=list,max_length=100)
    next_steps: list[str] = Field(default_factory=list,max_length=20)


def deliverable(child: dict[str,Any], specialist: str) -> dict[str,Any]:
    final = next((str(m['content']) for m in reversed(child['messages']) if m['role']=='ai' and m.get('content')),'')
    known = set(child['evidence_ids'])
    try:
        text = final.strip()
        if text.startswith('```'):
            text = text.split('\n',1)[1].rsplit('```',1)[0]
        value = Contribution.model_validate(json.loads(text))
        if not set(value.evidence_refs)<=known:
            raise ValueError('Unregistered evidence')
        data = dict(value.model_dump(),status='structured')
    except (ValueError,TypeError):
        data = dict(summary=final[:3000],findings=[],limitations=['La respuesta no cumple el contrato estructurado; no constituye un hallazgo validado.'],
            evidence_refs=list(known)[:100],next_steps=[],status='needs_structured_review')
    return dict(data,evidence_id='specialist:'+child['thread_id'],specialist=specialist,truncated=len(final)>3000)
