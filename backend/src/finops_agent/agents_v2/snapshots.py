import json
from typing import Any
import duckdb
import sqlglot
from sqlglot import exp
from ..config import atomic_write_text
from ..engine.incremental_inputs import digest
from .registry import use_cases
from .sql import query
from .reference_sql import reference_tree, bind_reference


def execute_case(client: Any, case_id: int, start: str, end: str, parameters: dict[str, Any] | None = None, *, all_dimensions: bool = False) -> dict[str, Any]:
    case = use_cases().get(case_id)
    if not case:
        raise ValueError('Use case desconocido.')
    tree = reference_tree(case['sql'][0])
    params, omitted = bind_reference(tree,start,end,parameters or {},all_dimensions)
    for group in tree.find_all(exp.Group):
        group.set('expressions',[item.this if isinstance(item,exp.Alias) else item for item in group.expressions])
    result = query(client,tree.sql(dialect='duckdb'),start,end,params)
    return {**result,'use_case_id':case_id,'reference_sql':case['sql'][0],'omitted_dimension_filters':omitted,'source':'use_case_query','status':'ok' if result['rowCount'] else 'empty'}


def signature(client: Any, start: str, end: str) -> str:
    from ..sources.remote_config import read_remote
    if read_remote(client):
        from ..sources.remote_query import adapter
        remote = adapter(client,start,end)
        try:
            return digest([client.profile.client_id,start,end,remote.revision,use_cases(),4])
        finally:
            remote.close()
    with client.engine.lock:
        batches = client.engine.conn.execute('SELECT file_hash FROM ingested_batches WHERE client_id=? ORDER BY file_hash',[client.profile.client_id]).fetchall()
    return digest([client.profile.client_id,start,end,client.profile.billing_currency,batches,use_cases(),3])


def read_snapshots(client: Any, start: str, end: str, ids: list[int] | None = None) -> dict[str, Any]:
    selected = sorted(set(use_cases() if ids is None else ids))
    if not selected or len(selected)>60 or any(key not in use_cases() for key in selected):
        raise ValueError('Selecciona use cases válidos del catálogo (máximo 60).')
    key = signature(client,start,end)
    path = client.workspace/'use_case_snapshots'/(key+'.json')
    with client.engine.lock:
        document = json.loads(path.read_text()) if path.exists() else dict(package_id=key,client_id=client.profile.client_id,
            period_start_utc=start,period_end_utc=end,results={})
        for case_id in selected:
            if str(case_id) not in document['results']:
                document['results'][str(case_id)] = snapshot_result(client,case_id,start,end)
        encoded = json.dumps(document,default=str,ensure_ascii=False)
        atomic_write_text(path,encoded)
        document = json.loads(encoded)
    results = [{**document['results'][str(case_id)],'rows':document['results'][str(case_id)].get('rows',[])[:5],
                    'preview_only':len(document['results'][str(case_id)].get('rows',[]))>5} for case_id in selected]
    return dict(evidence_id='use-cases:'+key,source='use_case_snapshot',client_id=client.profile.client_id,
        period_start_utc=start,period_end_utc=end,results=results,
        coverage={status:sum(row['status']==status for row in results) for status in ('ok','empty','unavailable','error')})


def snapshot_result(client: Any, case_id: int, start: str, end: str) -> dict[str, Any]:
    case = use_cases()[case_id]
    try:
        result = execute_case(client,case_id,start,end,all_dimensions=True)
    except (ValueError,sqlglot.errors.ParseError,duckdb.BinderException) as error:
        result = dict(status='unavailable',reason=str(error)[:800],rows=[])
    except duckdb.Error as error:
        result = dict(status='error',reason=str(error)[:800],rows=[])
    return {**result,'use_case_id':case_id,'title':case['title'],'capability':case['capability']}
