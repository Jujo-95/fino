import sqlglot
from sqlglot import exp


def validate_focus_sql(sql: str) -> str:
    statements = sqlglot.parse(sql, read="duckdb")
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError("Only one SELECT is allowed")
    tree = statements[0]
    if any(not isinstance(t.this, exp.Identifier) or t.name != "focus_usage" for t in tree.find_all(exp.Table)):
        raise ValueError("Only focus_usage may be read")
    if not list(tree.find_all(exp.Table)) or tree.find(exp.Func) and tree.find(exp.Anonymous):
        raise ValueError("Table functions and arbitrary functions are blocked")
    selects = list(tree.find_all(exp.Select))
    for select in selects:
        _validate_scope(select)
    return sql


def _validate_scope(select: exp.Select) -> None:
    where = select.args.get("where")
    if where is None or where.find(exp.Or) or where.find(exp.Not):
        raise ValueError("Conjunctive partition, tenant and currency predicates required")
    _require(where, "ChargePeriodStart", exp.GTE, "start_utc")
    _require(where, "ChargePeriodStart", exp.LT, "end_utc")
    _require(where, "BillingCurrency", exp.EQ, "currency")
    _require(where, "client_id", exp.EQ, "client_id")
    if any(isinstance(item, exp.Star) for item in select.expressions):
        raise ValueError("Explicit columns required")


def _require(where: exp.Expression, column: str, kind: type[exp.Expression], param: str) -> None:
    matches = [node for node in where.find_all(kind) if isinstance(node.this, exp.Column)
               and node.this.name.lower() == column.lower()
               and isinstance(node.expression, exp.Placeholder) and node.expression.name == param]
    if not matches:
        raise ValueError(f"Missing bound {column} predicate ({param})")
