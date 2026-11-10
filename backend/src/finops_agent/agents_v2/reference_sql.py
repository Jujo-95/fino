"""Deterministic dialect repair of imported reference SQL; original source preserved."""
import re
from typing import cast
import sqlglot
from sqlglot import exp


def reference_tree(sql: str) -> exp.Expression:
    sql = sql.replace('Â', '').replace('\u00a0',' ')
    sql = re.sub(r'Tags\["([^"\]]+)"\]',r"json_extract_string(Tags, '$.\1')",sql)
    sql = re.sub(r'(DATE\(ChargePeriodStart\))\s+AS\s+StartDay',r'\1',sql,flags=re.I)
    sql = sql.replace('JSON_UNQUOTE(JSON_EXTRACT(', 'json_extract_string(')
    sql = re.sub(r"(json_extract_string\([^)]*\))\)",r'\1',sql)
    sql = re.sub(r"JSON_CONTAINS_PATH\(([^,]+), 'all', '([^']+)', '([^']+)'\)",r"(json_extract(\1, '\2') IS NOT NULL AND json_extract(\1, '\3') IS NOT NULL)",sql)
    sql = sql.replace('AS UNSIGNED','AS UBIGINT')
    if 'ORDER BY' in sql and 'BillingPeriodStart DESC' in sql and 'GROUP BY' in sql:
        sql = sql.replace('BillingPeriodStart DESC','MIN(BillingPeriodStart) DESC')
    return cast(exp.Expression,sqlglot.parse_one(sql,read='duckdb'))


def bind_reference(tree: exp.Expression, start: str, end: str, parameters: dict,
                   all_dimensions: bool = False) -> tuple[dict,list[str]]:
    params, omitted = dict(parameters), []
    for index,item in enumerate(list(tree.find_all(exp.Placeholder))):
        parent = item.parent
        column = parent.this.name if parent is not None and isinstance(parent.this,exp.Column) else ''
        key = 'p'+str(index+1)
        if column.lower() in ('chargeperiodstart','chargeperiodend','billingperiodstart','billingperiodend'):
            params[key] = end if isinstance(parent,(exp.LT,exp.LTE)) else start
        elif key not in params and column in params:
            params[key] = params[column]
        elif key not in params and all_dimensions and isinstance(parent,exp.EQ):
            omitted.append(parent.sql())
            parent.replace(exp.true())
            continue
        item.replace(exp.Placeholder(this=key))
    return params, omitted
