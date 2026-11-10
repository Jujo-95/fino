from pathlib import Path
import pytest
from finops_agent.config import KB_DIR
from finops_agent.api.container import AppContainer
from finops_agent.models import ClientProfile
from finops_agent.sample_data import write_focus


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    return write_focus(tmp_path / "focus.csv")


@pytest.fixture
def container(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FINOPS_LLM_PROVIDER", "mock")
    c = AppContainer(tmp_path / "workspaces", KB_DIR)
    c.onboard(ClientProfile(client_id="acme", client_name="Acme FinTech", budget_policy={
        "total_monthly_budget_usd": 65000, "holdback_pct": 10}))
    yield c
    c.close()
