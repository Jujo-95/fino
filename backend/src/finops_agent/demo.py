from .api.container import AppContainer
from .models import ClientProfile, AllocationPolicy, BudgetPolicy
from .sample_data import write_focus


def seed() -> None:
    container = AppContainer()
    try:
        profile = ClientProfile(client_id="acme-demo", client_name="Acme FinTech", niche="DEMO · B2B Payments & AI",
            allocation_policy=AllocationPolicy(mode="Chargeback"), budget_policy=BudgetPolicy(total_monthly_budget_usd=75000, holdback_pct=10))
        client = container.onboard(profile)
        directory = client.workspace / "focus_exports"
        directory.mkdir(exist_ok=True)
        path = write_focus(directory / "demo-focus-october.csv")
        rows = client.engine.ingest_focus_csv(profile.client_id, path)
        print(f"Demo CSV ready: {rows} new rows. Synthetic data only. Run analysis from the UI.")
    finally:
        container.close()


if __name__ == "__main__":
    seed()
