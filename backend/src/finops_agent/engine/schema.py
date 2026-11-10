from .focus_columns import EXTRA_COLUMNS

COLUMNS = {
    "BillingAccountId": "VARCHAR", "SubAccountId": "VARCHAR", "SubAccountName": "VARCHAR",
    "ServiceName": "VARCHAR", "ServiceCategory": "VARCHAR", "ResourceId": "VARCHAR",
    "ResourceName": "VARCHAR", "RegionId": "VARCHAR", "ChargeCategory": "VARCHAR",
    "PricingCategory": "VARCHAR", "CommitmentDiscountId": "VARCHAR", "CommitmentDiscountType": "VARCHAR",
    "CommitmentDiscountStatus": "VARCHAR", "BillingCurrency": "VARCHAR",
    "BillingPeriodStart": "TIMESTAMP", "ChargePeriodStart": "TIMESTAMP", "ChargePeriodEnd": "TIMESTAMP",
    "ConsumedQuantity": "DOUBLE", "ConsumedUnit": "VARCHAR", "BilledCost": "DOUBLE",
    "EffectiveCost": "DOUBLE", "ListCost": "DOUBLE", "ContractedCost": "DOUBLE", "Tags": "JSON",
}
COLUMNS.update(EXTRA_COLUMNS)
REQUIRED = {"BillingAccountId", "SubAccountId", "ServiceName", "ServiceCategory", "ChargeCategory",
            "PricingCategory", "BillingCurrency", "BillingPeriodStart", "ChargePeriodStart",
            "ChargePeriodEnd", "BilledCost", "EffectiveCost", "ListCost", "ContractedCost", "Tags"}
KEYS = ["BillingPeriodStart", "ChargePeriodStart", "SubAccountId", "ServiceName", "ResourceId",
        "ChargeCategory", "CommitmentDiscountId", "CommitmentDiscountStatus"]
DDL = """
CREATE TABLE IF NOT EXISTS ingested_batches (
 client_id VARCHAR, file_hash VARCHAR, file_name VARCHAR, row_count BIGINT,
 ingested_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(client_id,file_hash));
CREATE TABLE IF NOT EXISTS tickets_ledger (
 fingerprint VARCHAR PRIMARY KEY, ticket_id VARCHAR UNIQUE, client_id VARCHAR, capability VARCHAR,
 status VARCHAR, document JSON);
CREATE TABLE IF NOT EXISTS context_documents (doc_id VARCHAR PRIMARY KEY, content VARCHAR);
"""

LEDGER_FIELDS = {
    "maturity_tier": "VARCHAR", "allocation_mode": "VARCHAR", "severity": "VARCHAR",
    "sub_account_id": "VARCHAR", "service_name": "VARCHAR", "period_bucket": "VARCHAR",
    "estimated_monthly_impact_usd": "DOUBLE", "billing_currency": "VARCHAR", "kpi_name": "VARCHAR",
    "kpi_value": "DOUBLE", "title": "VARCHAR", "resolution_note": "VARCHAR",
    "created_at_utc": "TIMESTAMP", "updated_at_utc": "TIMESTAMP",
}
