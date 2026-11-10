"""Portable aggregate queries share the local KPI definitions and summarizer."""
from typing import Any
from ..engine.analytics import summarize,detect_spikes
from ..engine.kpi_catalog import KPI_SQL_CATALOG,FILTER
from .parquet_remote import literal
from .result_cache import remote_result


def aggregate_sql(profile: Any) -> str:
    sql = KPI_SQL_CATALOG['totals']
    missing = ' OR '.join("coalesce(json_extract_string(Tags,"+literal('/'+tag)+"),'')=''" for tag in profile.allocation_policy.required_tags) or 'FALSE'
    shared = 'SubAccountId IN ('+','.join(literal(account) for account in profile.allocation_policy.shared_cost_sub_accounts)+')' if profile.allocation_policy.shared_cost_sub_accounts else 'FALSE'
    start = sql.index('        sum(CASE WHEN len(list_filter')
    end = sql.index('        sum(CASE WHEN lower(ServiceCategory)')
    return sql[:start]+f'''sum(CASE WHEN ({missing}) THEN EffectiveCost ELSE 0 END) AS unallocated,
        sum(CASE WHEN NOT ({shared}) AND NOT ({missing}) THEN EffectiveCost ELSE 0 END) AS direct,
        sum(CASE WHEN ({shared}) THEN EffectiveCost ELSE 0 END) AS shared,
        '''+sql[end:]


def analyze_remote(client: Any, start: str, end: str) -> dict[str,Any]:
    profile = client.profile
    from ..consulting.store import ConsultingStore
    confirmed = ConsultingStore(client).context()['values'].get('monthly_budget')
    if confirmed:
        profile = profile.model_copy(update={'budget_policy':profile.budget_policy.model_copy(update={'total_monthly_budget_usd':confirmed})})
    params = dict(client_id=profile.client_id,start_utc=start,end_utc=end,currency=profile.billing_currency)
    from .remote_query import adapter
    connection = adapter(client,start,end)
    try:
        from .retained_measurements import reuse
        retained = reuse(client,connection,profile,start,end,bool(confirmed))
        if retained:
            return retained
        results = {key:remote_result(client,aggregate_sql(profile) if key=='totals' else sql,params,start,end,connection)
                   for key,sql in KPI_SQL_CATALOG.items()}
        results['account_facts'] = remote_result(client,account_sql(profile),params,start,end,connection)
    finally:
        connection.close()
    totals = results['totals']['rows'][0]
    daily,services = results['daily']['rows'],results['services']['rows']
    # JSON cache round-trips dates and Decimal; normalize measured amounts only.
    for row in services:
        row['cost'],row['on_demand'] = float(row['cost']),float(row['on_demand'] or 0)
    for key,value in totals.items():
        if value is not None:
            totals[key] = float(value)
    overview = summarize(profile,totals,daily,services,detect_spikes(services),set(),start,end)
    from .remote_config import read_remote
    source = read_remote(client)
    assert source is not None
    return dict(overview,budget_confirmed=bool(confirmed),measurement_basis=totals,account_facts=results['account_facts']['rows'],source_config=source.model_dump(mode='json',exclude={'verified_at'}),query_evidence=[dict(query_id=k,source_revision=v['revision'],sql=v['sql'],
        parameters=v['parameters'],row_count=v['row_count'],complete=v['complete'],cache_hit=v['cache_hit'],execution=v.get('execution',{})) for k,v in results.items()])


def account_sql(profile: Any) -> str:
    tagged = ' AND '.join("coalesce(json_extract_string(Tags,"+literal('/'+tag)+"),'')<>''" for tag in profile.allocation_policy.required_tags) or 'TRUE'
    return '''SELECT SubAccountId AS account,CAST(ChargePeriodStart AS DATE) AS day,sum(EffectiveCost) AS cost,
        max(ChargePeriodEnd) AS through,count(*) AS rows,
        sum(CASE WHEN ResourceId IS NOT NULL AND ResourceId<>'' THEN 1 ELSE 0 END) AS resources,
        sum(CASE WHEN CommitmentDiscountId IS NOT NULL AND CommitmentDiscountId<>'' THEN 1 ELSE 0 END) AS commitments,
        sum(greatest(EffectiveCost,0)) AS positive_cost,
        sum(CASE WHEN '''+tagged+''' THEN greatest(EffectiveCost,0) ELSE 0 END) AS tagged_cost'''+FILTER+' GROUP BY 1,2 ORDER BY 1,2'
