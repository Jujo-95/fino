import json
import pytest
from fastapi.testclient import TestClient
from finops_agent.api.server import app
from finops_agent.api.routes import get_container
from finops_agent.agents import runtime_config
from finops_agent.agents.nvidia import settings


@pytest.fixture
def runtime_env(monkeypatch,tmp_path,container):
    values = {}
    class Vault:
        def get_password(self,service,account):
            return values.get((service,account))
        def set_password(self,service,account,value):
            values[(service,account)] = value
    monkeypatch.setattr(runtime_config,'_values',{})
    monkeypatch.setattr(runtime_config,'_source','environment')
    monkeypatch.setattr(runtime_config,'PATH',tmp_path/'runtime.json')
    monkeypatch.setattr(runtime_config,'ROOT',tmp_path)
    monkeypatch.setattr(runtime_config,'vault',lambda:Vault())
    (tmp_path/'.env').write_text('OTHER_SETTING=preserved\nNVIDIA_API_KEY=old-test-key\n')
    app.dependency_overrides[get_container] = lambda:container
    yield TestClient(app,base_url='http://127.0.0.1'),values
    app.dependency_overrides.clear()


def test_secure_rotation_updates_live_provider_without_leaking_key(runtime_env,container):
    http,vault = runtime_env
    body=dict(api_key='nvapi-runtime-test-key',model='nvidia/test-model',fallback_model='',persist_key=True)
    response=http.put('/api/v1/runtime/provider',headers={'X-Finops-Config':'1'},json=body)
    assert response.status_code==200 and response.json()['credential_source']=='keychain'
    provider=container.llm
    assert 'nvapi-runtime-test-key' not in response.text
    assert settings()['NVIDIA_API_KEY']=='nvapi-runtime-test-key'
    assert 'nvapi-runtime-test-key' not in runtime_config.PATH.read_text()
    assert 'NVIDIA_API_KEY' not in (runtime_config.ROOT/'.env').read_text()
    assert (runtime_config.ROOT/'.env').read_text()=='OTHER_SETTING=preserved\n'
    assert vault[(runtime_config.SERVICE,runtime_config.ACCOUNT)]=='nvapi-runtime-test-key'
    body.update(api_key='nvapi-second-test-key',model='nvidia/second-model')
    assert http.put('/api/v1/runtime/provider',headers={'X-Finops-Config':'1'},json=body).status_code==200
    assert container.llm is provider and provider.model=='nvidia/second-model'
    assert settings()['NVIDIA_API_KEY']=='nvapi-second-test-key'
    assert 'nvapi-second-test-key' not in http.get('/api/v1/runtime').text


@pytest.mark.parametrize('headers',[{}, {'X-Finops-Config':'1','Origin':'https://untrusted.invalid'}, {'X-Finops-Config':'1','Sec-Fetch-Site':'cross-site'}])
def test_runtime_changes_require_local_app_origin(runtime_env,headers):
    http,_=runtime_env
    assert http.put('/api/v1/runtime/provider',headers=headers,json=dict(api_key='nvapi-private-test',model='nvidia/test')).status_code==422
    assert not runtime_config.PATH.exists()


def test_invalid_request_and_keychain_failure_never_echo_or_persist_secret(runtime_env,monkeypatch):
    http,_=runtime_env
    response=http.put('/api/v1/runtime/provider',headers={'X-Finops-Config':'1'},json=dict(api_key='nvapi-private-test',model='invalid model'))
    assert response.status_code==422 and 'nvapi-private-test' not in response.text
    class FailingVault:
        def set_password(self,*args):
            raise RuntimeError('private backend detail')
    monkeypatch.setattr(runtime_config,'vault',lambda:FailingVault())
    response=http.put('/api/v1/runtime/provider',headers={'X-Finops-Config':'1'},json=dict(api_key='nvapi-private-test',model='nvidia/test'))
    assert response.status_code==422 and 'nvapi-private-test' not in response.text
    assert not runtime_config.PATH.exists() and not runtime_config.overrides()


def test_memory_only_mode_does_not_write_key_to_disk_or_vault(runtime_env):
    http,vault=runtime_env
    body=dict(api_key='nvapi-session-only-test',model='nvidia/test',persist_key=False)
    assert http.put('/api/v1/runtime/provider',headers={'X-Finops-Config':'1'},json=body).status_code==200
    assert not vault and settings()['NVIDIA_API_KEY']=='nvapi-session-only-test'
    assert 'nvapi-session-only-test' not in json.dumps(json.loads(runtime_config.PATH.read_text()))
