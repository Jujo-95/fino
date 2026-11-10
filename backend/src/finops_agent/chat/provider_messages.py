"""Persist native provider content in checkpoints, separate from public chat text."""
from typing import Any
from langchain_core.messages import convert_to_openai_messages,AIMessage


def provider_messages(messages: list[Any]) -> list[dict[str,Any]]:
    result = []
    for message in messages:
        converted = convert_to_openai_messages([message])[0]
        native = message.additional_kwargs.get('provider_content') if isinstance(message,AIMessage) else None
        if native:
            ids = {c['id'] for c in message.tool_calls}
            native = {**native,'parts':[p for p in native.get('parts',[]) if not p.get('function_call') or p['function_call'].get('id') in ids]}
            converted['provider_content'] = native
        result.append(converted)
    return result
