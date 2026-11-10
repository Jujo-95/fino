import csv
import json
from datetime import date, timedelta
from pathlib import Path
from .engine.schema import COLUMNS
from .lab.focus import enrich


def write_focus(path: Path, days: int = 20) -> Path:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(COLUMNS))
        writer.writeheader()
        for day in range(days):
            for account, service, daily in [("prod-payments", "Amazon EC2", 1500),
                    ("ml-platform", "Vertex AI", 600), ("shared-network", "Cloud Storage", 210)]:
                start = date(2026, 10, 1) + timedelta(days=day)
                cost = daily * (3 if day == days - 1 and service == "Vertex AI" else 1) + day * 3
                writer.writerow(enrich(focus_row(account, service, start, cost)))
    return path


def focus_row(account: str, service: str, start: date, cost: float) -> dict[str, object]:
    return dict(BillingAccountId="billing-01", SubAccountId=account, SubAccountName=account,
        ServiceName=service, ServiceCategory="AI" if "AI" in service else "Compute", ResourceId=service,
        ResourceName=service, RegionId="us-east-1", ChargeCategory="Usage", PricingCategory="On-Demand",
        CommitmentDiscountId="", CommitmentDiscountType="", CommitmentDiscountStatus="",
        BillingCurrency="USD", BillingPeriodStart="2026-10-01", ChargePeriodStart=str(start),
        ChargePeriodEnd=str(start + timedelta(days=1)), ConsumedQuantity=24, ConsumedUnit="hours",
        BilledCost=cost, EffectiveCost=cost, ListCost=cost * 1.22, ContractedCost=cost * 1.1,
        Tags=json.dumps({"owner": account, "env": "prod", "cost_center": "CC-1", "service": service}
                        if service != "Cloud Storage" else {}))
