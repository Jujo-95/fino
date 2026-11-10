"""Consulting consumes retained account/day aggregates, never empty local replicas."""
from datetime import date
from typing import Any
from ..engine.analysis_store import latest_analysis
from ..consulting.facts import missing_dates


def billing_facts(client: Any, context: dict[str,Any]) -> dict[str,Any]:
    value = latest_analysis(client)
    from .remote_config import read_remote
    source = read_remote(client)
    if value and source and value['overview'].get('source_config')!=source.model_dump(mode='json',exclude={'verified_at'}):
        value = None
    entries = value['overview'].get('account_facts',[]) if value else []
    rows = [(r['account'],date.fromisoformat(str(r['day'])[:10]),float(r['cost']),r['through'],int(r['rows']),int(r['resources']),int(r['commitments'])) for r in entries]
    days,accounts = sorted({r[1] for r in rows}),sorted({r[0] for r in rows})
    latency,cadence = context.get('data_latency_days'),context.get('source_cadence_days')
    positive = sum(float(r['positive_cost']) for r in entries)
    tagged = sum(float(r['tagged_cost']) for r in entries)
    owned = sum(float(r['positive_cost']) for r in entries if context.get('owners',{}).get(r['account']))
    latest = days[-1] if days else None
    return dict(row_count=sum(r[4] for r in rows),accounts=accounts,available_from=str(days[0]) if days else None,
        data_through=str(latest) if latest else None,observed_days=len(days),
        missing_days=missing_dates(rows,context.get('expected_accounts') or accounts,days),
        missing_accounts=sorted(set(context.get('expected_accounts',[]))-set(accounts)),
        freshness_known=latency is not None and cadence is not None,
        stale=bool(latest and cadence and latency is not None and (date.today()-latest).days>latency+cadence),
        resource_rows=sum(r[5] for r in rows),commitment_rows=sum(r[6] for r in rows),
        allocation=dict(tagged_cost_pct=tagged/positive*100 if positive else None,owned_cost_pct=owned/positive*100 if positive else None,
            positive_cost=positive,method='Positive cost; retained account/day aggregates; confirmed owners evaluated separately.'),
        fingerprint=value['source_revision'] if value else 'remote-not-analyzed',focus_validation='internal_checks_only',reconciliation='not_verified')
