import json
from functools import lru_cache
from typing import Any
from ..config import ROOT

ORCHESTRATOR = 'v2-finops-report-orchestrator'
DIRECTORY = ROOT/'prompts/agents-v2'


@lru_cache(maxsize=1)
def definitions() -> dict[str, dict[str, Any]]:
    return {row['key']:row for row in json.loads((DIRECTORY/'registry.json').read_text())}


@lru_cache(maxsize=1)
def use_cases() -> dict[int, dict[str, Any]]:
    return {row['id']:row for row in json.loads((DIRECTORY/'use-cases.json').read_text())}


def public_agents() -> list[dict[str, Any]]:
    keys = ('key','name','original_name','role','avatar','generation','capability','use_case_ids')
    return [{key:row[key] for key in keys} for row in definitions().values()]


def system_prompt(agent_id: str, include_specialty: bool | None = None) -> str:
    row = definitions()[agent_id]
    if include_specialty is None:
        adapter = (DIRECTORY/'app-adapter.md').read_text()
        base = (DIRECTORY/'orchestrator-runtime.md').read_text() if agent_id == ORCHESTRATOR else row['prompt']
        return base+'\n\n# App runtime contract (takes precedence over source deployment instructions)\n'+adapter+'\n'+(DIRECTORY/'consulting.md').read_text()
    if agent_id == ORCHESTRATOR:
        base = (DIRECTORY/'fino-core.md').read_text()
    else:
        base = (DIRECTORY/'specialist-core.md').read_text()
        if include_specialty:
            base += '\n\n# Reglas de la especialidad solicitada\n' + row['prompt']
    return base+'\n\n'+(DIRECTORY/'app-adapter-core.md').read_text()+'\n'+(DIRECTORY/'consulting-core.md').read_text()
