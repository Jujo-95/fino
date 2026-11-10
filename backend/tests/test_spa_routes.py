from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from finops_agent.api.spa import SPAStaticFiles


@pytest.mark.parametrize(
    "path,status",
    [
        ("/clients/acme/tickets/FIN-011?mode=focus", 200),
        ("/clients/acme/chat/thread-123?ticket=FIN-011", 200),
        ("/clients/acme/reports/run-123", 200),
        ("/clients/acme/connections?source=focus", 200),
        ("/assets/missing.js", 404),
        ("/api/v1/missing", 404),
        ("/clients/acme/missing.js", 404),
    ],
)
def test_spa_reload_preserves_api_and_asset_errors(tmp_path, path, status):
    (tmp_path / "index.html").write_text("<html>finops app</html>")
    app = FastAPI()
    app.mount("/", SPAStaticFiles(directory=tmp_path, html=True))
    with TestClient(app) as client:
        response = client.get(path)
        assert response.status_code == status
        if status == 200:
            assert "finops app" in response.text
