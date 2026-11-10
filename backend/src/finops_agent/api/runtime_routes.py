from typing import Any
from .routes import router, Container
from fastapi import Request
from ..agents import runtime_config
from ..engine.script_store import ScriptStore


@router.get('/runtime')
def runtime(c: Container) -> dict[str, Any]:
    if hasattr(c.llm,'readiness'):
        return {**runtime_config.public(), **c.llm.readiness(), 'context_strategy': 'structured_documents',
                'data_source': 'local_focus_csv', 'live_verified': bool(c.llm.verified_at)}
    return dict(provider='rules' if c.llm is None else type(c.llm).__name__,
                configured=c.llm is not None, mode='rules' if c.llm is None else 'legacy_commentary',
                context_strategy='structured_documents', data_source='local_focus_csv')


@router.post('/runtime/check')
async def check_provider(request: Request, c: Container) -> dict[str, Any]:
    from .provider_routes import local_write
    local_write(request)
    if not hasattr(c.llm,'readiness'):
        raise ValueError('Configura un proveedor con herramientas para comprobar la conexión')
    from ..agents.tool_catalog import tool
    c.request_limits.admit('runtime-check',3,0,1)
    result = await c.llm.complete_for_report([dict(role='user', content='Call connectivity_check with value=ok.')],
        [tool('connectivity_check', 'Verify native tool calls', dict(value=dict(type='string', enum=['ok'])), ['value'])],max_tokens=128)
    calls = result['message'].get('tool_calls', [])
    import json
    valid = any(call['function']['name'] == 'connectivity_check' and
                json.loads(call['function']['arguments']) == {'value': 'ok'} for call in calls)
    if not valid:
        raise ValueError('El proveedor respondió pero no confirmó la herramienta de prueba')
    return dict(status='verified', model=result.get('model',c.llm.model), native_tool_calling=True, usage=result['usage'])


@router.get('/clients/{client_id}/scripts')
def scripts(client_id: str, c: Container, run_id: str | None = None) -> list[dict[str, Any]]:
    return ScriptStore(c.client(client_id).engine).list(run_id)


@router.get('/clients/{client_id}/scripts/{snapshot_id}')
def script_detail(client_id: str, snapshot_id: str, c: Container) -> dict[str, Any]:
    return ScriptStore(c.client(client_id).engine).read(snapshot_id)
