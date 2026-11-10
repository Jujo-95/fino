"""Page reads use retained aggregates, never start cloud scans as a side effect."""
from typing import Any
from ..engine.analysis_store import latest_analysis
from ..engine.analytics import summarize
from .remote_config import read_remote


def remote_overview(client: Any) -> dict[str,Any]:
    latest = latest_analysis(client)
    source = read_remote(client)
    assert source is not None
    if latest and latest['overview'].get('source_config')==source.model_dump(mode='json',exclude={'verified_at'}):
        return dict(latest['overview'],analysis_id=latest['analysis_id'])
    end = source.available_end
    start = max(source.available_start,end.replace(day=1))
    if start>=end:
        start = source.available_start
    totals = dict(actual=0,observed_days=0,usage=None,commitment=None,used_commitment=None,
        unallocated=None,direct=None,ai_total=None,equivalent=None)
    value = summarize(client.profile,totals,[],[],[],set(),str(start),str(end))
    value['metrics'] = [dict(metric,value=None) for metric in value['metrics']]
    return dict(value,source_pending=True,budget_confirmed=False)
