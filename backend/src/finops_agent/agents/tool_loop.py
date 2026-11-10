import asyncio
import json
from typing import Any
from .tool_catalog import read_tools
from .agent_output import submit_tool, validate_output


async def run_loop(provider: Any, messages: list[dict[str, Any]], tools: Any, spec: Any) -> dict[str, Any]:
    usage: list[dict[str, Any]] = []
    definitions = [*read_tools(), submit_tool(spec, tools.state["kpi_snapshots"]["metrics"])]
    if hasattr(tools, "refine"):
        from .synthesis_agent import refinement_tool
        definitions.append(refinement_tool())
    async with asyncio.timeout(600):
        for _ in range(10):
            tools.checkpoint(messages, usage)
            completion = getattr(provider,'complete_for_report',provider.complete)
            reply = await completion(messages, definitions)
            usage.append({**reply.get("usage",{}),**{key:reply.get(key) for key in ("model","requested_model","fallback","fallback_reason")}})
            message = reply["message"]
            messages.append(message)
            tools.checkpoint(messages, usage)
            calls = message.get("tool_calls") or []
            if not calls:
                messages.append(dict(role="user", content="Use the tools, then submit_analysis. Free text is not a submission."))
                continue
            if len(calls) > 8:
                raise ValueError("Too many tool calls in one turn")
            submitted = None
            for call in calls:
                result = await dispatch_call(call, tools, spec)
                messages.append(dict(role="tool", tool_call_id=call["id"], content=json.dumps(
                    result["response"], default=str, ensure_ascii=False)))
                if result.get("output") is not None:
                    submitted = result["output"]
            if submitted is not None:
                return dict(output=submitted, messages=messages, usage=usage,models=list(dict.fromkeys(item["model"] for item in usage if item.get("model"))),tool_definitions=definitions)
    raise ValueError("Agent exceeded tool rounds without a valid evidenced submission")


def process_call(call: dict[str, Any], tools: Any, spec: Any) -> dict[str, Any]:
    try:
        name = call["function"]["name"]
        args = json.loads(call["function"]["arguments"])
        if not isinstance(args, dict):
            raise ValueError("Tool arguments must be an object")
        if name == "submit_analysis":
            output = validate_output(args, tools, spec)
            tools.calls.append(dict(tool=name, tool_call_id=call["id"], status="accepted"))
            return dict(response={"accepted": True}, output=output)
        return dict(response=tools.execute(name, args, call["id"]))
    except (ValueError, KeyError, TypeError) as exc:
        tools.calls.append(dict(tool=call.get("function", {}).get("name"), status="rejected", error=str(exc)))
        return dict(response={"error": str(exc), "retry": True})


async def dispatch_call(call: dict[str, Any], tools: Any, spec: Any) -> dict[str, Any]:
    if call.get("function", {}).get("name") != "request_refinement" or not hasattr(tools, "refine"):
        return await asyncio.to_thread(process_call, call, tools, spec)
    try:
        args = json.loads(call["function"]["arguments"])
        result = await tools.refine(args)
        tools.calls.append(dict(tool="request_refinement", arguments=args, tool_call_id=call["id"]))
        return dict(response=result)
    except (ValueError, KeyError, TypeError) as exc:
        return dict(response={"error": str(exc)})
