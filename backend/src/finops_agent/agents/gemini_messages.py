"""Translate the existing provider contract while preserving opaque Gemini signatures."""
import json
from typing import Any
from uuid import uuid4
from google.genai import types


def contents(messages: list[dict[str,Any]]) -> list[types.Content]:
    result: list[types.Content] = []
    names = {c['id']:c['function']['name'] for m in messages for c in m.get('tool_calls',[])}
    for message in messages:
        role = message['role']
        if role=='system':
            continue
        if message.get('provider_content'):
            content = types.Content.model_validate(message['provider_content'])
        elif role=='tool':
            key = message['tool_call_id']
            content = types.Content(role='user',parts=[types.Part(function_response=types.FunctionResponse(
                id=key,name=names.get(key) or message.get('name'),response={'result':parse(message.get('content',''))}))])
        elif role=='assistant':
            parts = [types.Part(text=message['content'])] if message.get('content') else []
            parts += [types.Part(thought_signature=b'skip_thought_signature_validator',function_call=types.FunctionCall(id=c['id'],name=c['function']['name'],
                args=json.loads(c['function']['arguments']))) for c in message.get('tool_calls',[])]
            content = types.Content(role='model',parts=parts)
        else:
            content = types.Content(role='user',parts=[types.Part(text=str(message.get('content','')))])
        if not content.parts:
            continue
        if result and result[-1].role==content.role:
            result[-1].parts = [*(result[-1].parts or []),*content.parts]
        else:
            result.append(content)
    return result


def parse(value: str) -> Any:
    try:
        return json.loads(value)
    except (ValueError,TypeError):
        return value


def generation_config(messages: list[dict[str,Any]], tools: list[dict[str,Any]], maximum: int) -> types.GenerateContentConfig:
    declarations = [types.FunctionDeclaration(name=t['function']['name'],description=t['function'].get('description',''),
        parameters_json_schema=t['function'].get('parameters',{})) for t in tools]
    return types.GenerateContentConfig(system_instruction='\n'.join(str(m.get('content','')) for m in messages if m['role']=='system'),
        tools=[types.Tool(function_declarations=declarations)] if declarations else None,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),temperature=.5,max_output_tokens=maximum)


def result_message(parts: list[types.Part]) -> dict[str,Any]:
    safe = [p for p in parts if not p.thought]
    calls = []
    for part in safe:
        if part.function_call:
            call = part.function_call
            if not call.id:
                call.id = uuid4().hex
            calls.append(dict(id=call.id,type='function',function=dict(name=call.name,arguments=json.dumps(call.args or {}))))
    result: dict[str,Any] = dict(role='assistant',content=''.join(p.text or '' for p in safe),
        provider_content=types.Content(role='model',parts=safe).model_dump(mode='json',exclude_none=True))
    if calls:
        result['tool_calls'] = calls
    return result
