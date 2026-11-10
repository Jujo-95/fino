import json
from collections.abc import AsyncIterator
from typing import Any
from fastapi import Request
from ..models import RunRequest
from .container import AppContainer


def frame(node: str, payload: dict[str, Any], run_id: str) -> str:
    return f"data: {json.dumps({'node': node, 'payload': payload, 'run_id': run_id}, default=str)}\n\n"


async def audit_events(body: RunRequest, request: Request, c: AppContainer, record: dict[str,Any] | None = None) -> AsyncIterator[str]:
    record = record or c.jobs.start(body)
    async for event in c.jobs.subscribe(body.client_id, record['run_id']):
        if event['node'] == '__heartbeat__':
            yield ': heartbeat\n\n'
        else:
            yield frame(event['node'], event['payload'], event['run_id'])
