import json
from time import perf_counter
from typing import Any
from uuid import uuid4
from .audit_trace import timestamp
from .tool_catalog import QUERY_SQL
from ..engine.kpi_catalog import KPI_SPECS
from ..engine.schema import COLUMNS
from dataclasses import asdict
from ..engine.script_store import ScriptStore
from ..config import atomic_write_text


class AgentTools:
    def __init__(self, container: Any, state: dict[str, Any], node: str) -> None:
        self.container, self.state, self.node = container, state, node
        self.client = container.client(state["client_id"])
        self.queries: list[dict[str, Any]] = []
        self.calls: list[dict[str, Any]] = []
        self.evidence: dict[str, Any] = {}

    def execute(self, name: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
        started, success = perf_counter(), False
        result: dict[str, Any] = {}
        try:
            if name == "describe_data" and not args:
                result = dict(evidence_id="schema:"+uuid4().hex, columns=COLUMNS, queries=list(QUERY_SQL),
                    metrics={key: asdict(spec) for key, spec in KPI_SPECS.items()})
            elif name == "query_focus":
                result = self.query(args)
            elif name == "read_scripts" and not args:
                result = self.scripts()
            elif name == "read_context" and not args:
                result = self.context()
            else:
                raise ValueError("Unknown tool or unexpected arguments")
            self.evidence[str(result["evidence_id"])] = result
            success = True
            return result
        finally:
            self.calls.append(dict(tool=name, arguments=args, tool_call_id=call_id,
                status="completed" if success else "failed", evidence_id=result.get("evidence_id"),
                duration_ms=round((perf_counter()-started)*1000, 3)))

    def query(self, args: dict[str, Any]) -> dict[str, Any]:
        if not set(args) <= {"query_id", "account", "service"} or args.get("query_id") not in QUERY_SQL:
            raise ValueError("Choose a query_id from the allowlisted catalog")
        name, started = args["query_id"], perf_counter()
        params = dict(client_id=self.state["client_id"], start_utc=self.state["period_start_utc"],
                      end_utc=self.state["period_end_utc"], currency=self.state["billing_currency"])
        if name in ("totals", "tag_gaps"):
            policy = self.client.profile.allocation_policy
            params["required_tags"] = policy.required_tags
            if name == "totals":
                params["shared_accounts"] = policy.shared_cost_sub_accounts
        sql, params = scoped_sql(QUERY_SQL[name], params, args)
        rows = self.client.engine.bounded_query(sql, params)
        query = dict(query_id=uuid4().hex, name=name, sql=sql, parameters=params, executed_by=self.node,
            source="agent_tool", executed_at_utc=timestamp(), duration_ms=round((perf_counter()-started)*1000, 3),
            row_count=len(rows), sample_rows=rows[:100], sample_limit=100, truncated=len(rows)>100, status="completed")
        self.queries.append(query)
        return dict(evidence_id=query["query_id"], rows=rows[:100], truncated=len(rows)>100,
                    sql=sql, parameters=params, source="agent_tool", row_count=len(rows))

    def scripts(self) -> dict[str, Any]:
        snapshot_id = self.state["kpi_snapshots"]["snapshot_id"]
        snapshot = ScriptStore(self.client.engine).read(snapshot_id)
        excluded = {"query_evidence", "context_evidence"}
        return dict(evidence_id="script:"+snapshot_id, source="script_snapshot",
                    data={key: value for key, value in snapshot.items() if key not in excluded})

    def context(self) -> dict[str, Any]:
        with self.client.engine.lock:
            rows = self.client.engine.conn.execute("SELECT doc_id,content FROM context_documents "
                "WHERE NOT starts_with(doc_id,'report:') ORDER BY doc_id LIMIT 100").fetchall()
        docs = [dict(doc_id=row[0], text=row[1][:12000], source="client_context") for row in rows]
        return dict(evidence_id="context:"+uuid4().hex, documents=docs, truncated=len(rows)==100,
                    profile=self.client.profile.model_dump(mode="json"))

    def checkpoint(self, messages: list[dict[str, Any]], usage: list[dict[str, Any]]) -> None:
        if self.state.get("run_id"):
            path = self.client.workspace / "audit_runs/progress" / (self.state["run_id"] + ".json")
            atomic_write_text(path, json.dumps(dict(node=self.node, updated_at_utc=timestamp(),
                queries=self.queries, tool_calls=self.calls, messages=messages, usage=usage), default=str))

    def serialized(self, result: dict[str, Any]) -> str:
        return json.dumps(result, default=str, ensure_ascii=False)


def scoped_sql(sql: str, params: dict[str, Any], args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    predicates = []
    for key, column in (("account", "SubAccountId"), ("service", "ServiceName")):
        if key in args:
            if not isinstance(args[key], str) or len(args[key]) > 256:
                raise ValueError("Invalid account/service filter")
            predicates.append(f" AND {column}=${key} ")
            params[key] = args[key]
    index = min((sql.index(token) for token in ("GROUP BY", "ORDER BY", "LIMIT") if token in sql), default=len(sql))
    return sql[:index] + "".join(predicates) + sql[index:], params
