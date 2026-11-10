import json
from datetime import date
from pathlib import Path
from typing import Any
import pytest
from finops_agent.api.container import AppContainer
from finops_agent.lab.runtime import prepare
from finops_agent.lab.storage import bootstrap, publish
from finops_agent.sources.models import load_source, S3Source
from finops_agent.sources.s3 import sync, sdk, configure


@pytest.fixture()
def laboratory(tmp_path: Path, monkeypatch: Any) -> Any:
    pytest.importorskip('moto.server')
    from moto.server import ThreadedMotoServer
    from moto import settings
    monkeypatch.setenv('FINOPS_LLM_PROVIDER','mock')
    root,workspaces = tmp_path/'.lab',tmp_path/'workspaces'
    prepare(root,workspaces,date(2026,7,23),90,42)
    from moto import backends
    for name in ['iam','s3']:
        backends.get_backend(name).reset()
    old = settings.INITIAL_NO_AUTH_ACTION_COUNT
    server = ThreadedMotoServer(ip_address='127.0.0.1',port=0,verbose=False)
    server.start()
    host,port = server.get_host_and_port()
    bootstrap(root,workspaces,f'http://{host}:{port}')
    container = AppContainer(workspaces=workspaces)
    try:
        yield root,container
    finally:
        container.close()
        server.stop()
        settings.INITIAL_NO_AUTH_ACTION_COUNT = old


def test_s3_duckdb_incremental_and_permissions(laboratory: Any) -> None:
    root,c = laboratory
    publish(root,'lab-fintech',3)
    publish(root,'lab-commerce',2)
    a,b = c.client('lab-fintech'),c.client('lab-commerce')
    assert sync(a,date(2026,7,24))['ingested_rows']==12
    assert sync(a)['ingested_rows']==6
    assert sync(a)['ingested_rows']==0
    publish(root,'lab-fintech',4)
    assert sync(a)['ingested_rows']==6
    assert sync(b)['ingested_rows']==12
    source,key = load_source(a.workspace)
    remote = sdk(source,key)
    with pytest.raises(Exception):
        remote.get_object(Bucket='finops-lab-commerce',Key='focus/v2/2026/07/23/usage.csv')
    with pytest.raises(Exception):
        remote.put_object(Bucket=source.bucket,Key='focus/forbidden.csv',Body=b'x')
    configure(a.engine.conn,source.model_copy(update={'bucket':'finops-lab-commerce'}),key)
    try:
        with pytest.raises(Exception):
            a.engine.conn.execute("SELECT * FROM read_csv_auto('s3://finops-lab-commerce/focus/v2/2026/07/23/usage.csv')")
    finally:
        a.engine.conn.execute('DROP SECRET finops_source')
    assert a.engine.conn.execute('SELECT count(*) FROM source_objects').fetchone()[0]==4
    assert a.engine.conn.execute('SELECT count(*) FROM focus_usage').fetchone()[0]==24
    assert b.engine.conn.execute('SELECT count(*) FROM focus_usage').fetchone()[0]==12
    assert a.engine.conn.execute("SELECT count(*) FROM focus_usage WHERE ResourceId NOT LIKE 'lab-fintech/%'").fetchone()[0]==0
    assert 'secret' not in json.loads((a.workspace/'source-status.json').read_text())


def test_restart_rehydrates_and_validation_failure_rolls_back(laboratory: Any) -> None:
    root,c = laboratory
    client = c.client('lab-fintech')
    publish(root,'lab-fintech',1)
    assert sync(client)['ingested_rows']==6
    from moto import backends
    for name in ['iam','s3']:
        backends.get_backend(name).reset()
    source,_ = load_source(client.workspace)
    bootstrap(root,c.workspaces,source.endpoint)
    publish(root,'lab-fintech',1,restore=True)
    assert sync(client)['ingested_rows']==0
    credentials = json.loads((root/'publisher.json').read_text())
    from finops_agent.lab.storage import aws
    writer = aws('s3',credentials.pop('endpoint'),credentials)
    writer.put_object(Bucket='finops-lab-fintech',Key='focus/v2/2026/07/24/usage.csv',Body=b'bad\n1\n')
    with pytest.raises(ValueError):
        sync(client)
    assert client.engine.conn.execute('SELECT count(*) FROM focus_usage').fetchone()[0]==6
    assert client.engine.conn.execute('SELECT count(*) FROM source_objects').fetchone()[0]==1
    assert not client.engine.conn.execute("SELECT name FROM duckdb_secrets() WHERE name='finops_source'").fetchall()
    original = (root/'lab-fintech/focus/v2/2026/07/23/usage.csv').read_bytes()
    writer.put_object(Bucket='finops-lab-fintech',Key='focus/v2/2026/07/24/usage.csv',Body=original)
    with pytest.raises(ValueError):
        sync(client)
    writer.put_object(Bucket='finops-lab-fintech',Key='focus/v2/2026/07/23/usage.csv',Body=original+b'\n')
    with pytest.raises(ValueError):
        sync(client)
    assert client.engine.conn.execute('SELECT count(*) FROM focus_usage').fetchone()[0]==6


@pytest.mark.parametrize('changes',[{'endpoint':'http://example.com'}, {'endpoint':'https://user:pass@example.com'},
    {'prefix':'../'}, {'prefix':'focus/*/'}, {'bucket':"bucket';"}])
def test_invalid_source_config(changes: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        S3Source.model_validate(dict(client_id='lab-fintech',endpoint='http://127.0.0.1:9000',bucket='finops-lab-fintech')|changes)


def test_source_http_and_advance_is_not_replayed(laboratory: Any, monkeypatch: Any) -> None:
    from fastapi.testclient import TestClient
    from finops_agent.api.server import app
    from finops_agent.api.routes import get_container
    from finops_agent import config
    root,c = laboratory
    monkeypatch.setattr(config,'ROOT',root.parent)
    publish(root,'lab-fintech',3)
    app.dependency_overrides[get_container] = lambda:c
    try:
        http = TestClient(app)
        url = '/api/v1/clients/lab-fintech/source'
        assert http.post(url+'/sync',json={}).json()['ingested_rows']==18
        source = http.get(url).json()
        assert source['laboratory']['days']==3
        assert 'secret' not in json.dumps(source).lower()
        result = http.post(url+'/advance',json={'expected_days':3})
        assert result.status_code==200 and result.json()['sync']['ingested_rows']==6
        assert http.post(url+'/advance',json={'expected_days':3}).status_code==422
        assert http.get(url).json()['laboratory']['days']==4
        assert http.get('/api/v1/clients/absent/source').status_code==404
    finally:
        app.dependency_overrides.clear()
