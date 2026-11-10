from typing import Any
from time import perf_counter
from .audit_trace import append_trace, specialist_trace, timestamp
from ..models import FinOpsGraphState
from .recommendations import recommendations
from .specs import SpecialistSpec, SPECIALIST_SPECS
from .agent_execution import execute_specialist


class SpecialistRunner:
    def __init__(self, spec: SpecialistSpec, container: Any) -> None:
        self.spec, self.container = spec, container

    async def __call__(self, state: FinOpsGraphState) -> dict[str, Any]:
        if getattr(self.container.llm,'native_tools',False):
            return await execute_specialist(self.container, self.spec, state)
        started, started_at = perf_counter(), timestamp()
        overview = state["kpi_snapshots"]
        results = recommendations(self.spec, overview)
        llm: dict[str, Any] = {}
        commentary = dict(state.get("specialist_commentary", {}))
        if self.container.llm is not None:
            llm = await self._enrich(state, overview)
            commentary[self.spec.name] = llm["llm_output"]
        update: dict[str, Any] = {"findings": state.get("findings", []) + [result.model_dump() for result in results]}
        if self.spec.name == "Anomaly":
            update["active_anomalies"] = [row["key"] for row in overview["spikes"]]
            update["excluded_baseload"] = overview["excluded_baseload"]
        update["specialist_commentary"] = commentary
        name = next(name for name, spec in SPECIALIST_SPECS.items() if spec == self.spec)
        trace = specialist_trace(name, self.spec, dict(state), [result.model_dump() for result in results],
                                 started, started_at, self.container, llm)
        update["audit_traces"] = append_trace(dict(state), trace)
        return update

    async def _enrich(self, state: FinOpsGraphState, overview: dict[str, Any]) -> dict[str, Any]:
        # External models supply commentary only; deterministic calculations control actions.
        guidelines = self.container.memory.retrieve(self.spec.capability_slug)
        client = self.container.memory.retrieve(self.spec.reasoning_focus, state["client_id"])
        messages = [
            ("system", f"{self.spec.reasoning_focus}\nGuidelines: {guidelines}\nDo not execute actions."),
            ("human", f"Client context: {client}\nKPIs: {overview['metrics']}"),
        ]
        async with self.container.llm_semaphore:
            response = await self.container.llm.ainvoke(messages)
        return dict(engine="rules_with_llm_commentary", llm_output=str(response.content),
                    prompt={"messages": [{"role": role, "content": content} for role, content in messages]},
                    context=[{**item, "source": "finops_kb"} for item in guidelines]
                            + [{**item, "source": "client_memory"} for item in client])
