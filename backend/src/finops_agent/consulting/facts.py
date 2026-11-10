from datetime import date, timedelta
from typing import Any
from ..engine.incremental_inputs import digest


def billing_facts(client: Any, context: dict[str, Any]) -> dict[str, Any]:
    from ..sources.remote_config import read_remote
    if read_remote(client):
        from ..sources.remote_facts import billing_facts as retained_facts
        return retained_facts(client,context)
    with client.engine.lock:
        rows = client.engine.conn.execute('SELECT SubAccountId, CAST(ChargePeriodStart AS DATE), '
            'sum(EffectiveCost), max(ChargePeriodEnd), count(*), '
            "count(*) FILTER (WHERE ResourceId IS NOT NULL AND ResourceId<>''), "
            "count(*) FILTER (WHERE CommitmentDiscountId IS NOT NULL AND CommitmentDiscountId<>'') "
            'FROM focus_usage WHERE client_id=? AND BillingCurrency=? GROUP BY 1,2 ORDER BY 1,2',
            [client.profile.client_id, client.profile.billing_currency]).fetchall()
        batches = client.engine.conn.execute('SELECT file_hash FROM ingested_batches WHERE client_id=? ORDER BY file_hash',
                                             [client.profile.client_id]).fetchall()
    days = sorted({row[1] for row in rows})
    accounts = sorted({row[0] for row in rows})
    expected = context.get('expected_accounts')
    cadence = context.get('source_cadence_days')
    latency = context.get('data_latency_days')
    missing = missing_dates(rows, expected or accounts, days)
    acknowledged = context.get('non_billable_days', {})
    missing = {a:[d for d in dates if d not in acknowledged.get(a, [])] for a,dates in missing.items()}
    missing = {a:dates for a,dates in missing.items() if dates}
    latest = days[-1] if days else None
    return dict(row_count=sum(r[4] for r in rows), accounts=accounts,
        available_from=str(days[0]) if days else None, data_through=str(latest) if latest else None,
        observed_days=len(days), missing_days=missing, missing_accounts=sorted(set(expected or [])-set(accounts)),
        freshness_known=cadence is not None and latency is not None,
        stale=bool(latest and cadence and latency is not None and (date.today()-latest).days>cadence+latency),
        resource_rows=sum(r[5] for r in rows), commitment_rows=sum(r[6] for r in rows),
        allocation=allocation_facts(client, context), fingerprint=digest([rows, batches]),
        focus_validation='internal_checks_only', reconciliation='not_verified')


def missing_dates(rows: list[Any], accounts: list[str], days: list[date]) -> dict[str, list[str]]:
    if not days:
        return {}
    # Internal gaps only: billing does not prove every account must spend every day.
    result = {}
    for account in accounts:
        observed = {r[1] for r in rows if r[0] == account}
        if len(observed) < 2:
            continue
        start, end = min(observed), max(observed)
        missing = [str(start+timedelta(days=i)) for i in range((end-start).days+1)
                   if start+timedelta(days=i) not in observed]
        if missing:
            result[account] = missing[:31]
    return result


def allocation_facts(client: Any, context: dict[str, Any]) -> dict[str, Any]:
    owners = context.get('owners', {})
    tags = client.profile.allocation_policy.required_tags
    with client.engine.lock:
        rows = client.engine.conn.execute('SELECT SubAccountId, Tags, sum(greatest(EffectiveCost,0)) '
            'FROM focus_usage WHERE client_id=? AND BillingCurrency=? GROUP BY 1,2',
            [client.profile.client_id, client.profile.billing_currency]).fetchall()
    import json
    total = sum(float(r[2]) for r in rows)
    tagged = sum(float(cost) for _, raw, cost in rows if all(str(json.loads(raw).get(tag) or '').strip() for tag in tags))
    assigned = sum(float(cost) for account, _, cost in rows if owners.get(account))
    return dict(tagged_cost_pct=tagged/total*100 if total else None,
        owned_cost_pct=assigned/total*100 if total else None, positive_cost=total,
        method='Confirmed account owner; tags separately checked. Credits excluded; zero denominator unavailable.')
