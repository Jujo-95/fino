# 02 — Data, Storage & Memory Schemas

## 1. Workspace Directory Layout per Client
```text
workspaces/<client_id>/
├── client_profile.yaml          # Structured client config, budgets, holdbacks, tag policy
├── context_notes/               # Unstructured business context (.md) indexed in HippoRAG
├── focus_exports/               # Raw daily FOCUS CSV exports
├── tickets/                     # Atomic Markdown tickets (FIN-001.md, FIN-002.md...)
├── reports/                     # Generated daily/onboarding reports (YYYY-MM-DD.md)
└── storage/
    ├── finops.duckdb            # Transactional analytical & ledger database
    └── hipporag_client_index/   # Episodic HippoRAG graph storage for this client
```

## 2. DuckDB Relational & Analytical DDL (`finops.duckdb`)
All tables use UTC timestamps and explicit `BillingCurrency`.

```sql
CREATE TABLE IF NOT EXISTS ingested_batches (
    client_id VARCHAR NOT NULL,
    file_hash VARCHAR NOT NULL,
    file_name VARCHAR NOT NULL,
    row_count BIGINT NOT NULL,
    ingested_at_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (client_id, file_hash)
);

CREATE TABLE IF NOT EXISTS focus_usage (
    client_id VARCHAR NOT NULL,
    file_hash VARCHAR NOT NULL,
    BillingAccountId VARCHAR NOT NULL,
    SubAccountId VARCHAR NOT NULL,
    SubAccountName VARCHAR,
    ServiceName VARCHAR NOT NULL,
    ServiceCategory VARCHAR NOT NULL,
    ResourceId VARCHAR,
    ResourceName VARCHAR,
    RegionId VARCHAR,
    ChargeCategory VARCHAR NOT NULL,          -- 'Usage' | 'Purchase' | 'Tax' | 'Credit' | 'Adjustment'
    PricingCategory VARCHAR NOT NULL,         -- 'On-Demand' | 'Commitment-Based' | 'Spot' | 'Other'
    CommitmentDiscountId VARCHAR,
    CommitmentDiscountType VARCHAR,           -- 'Savings Plan' | 'Reserved Instance' | 'CUD'
    CommitmentDiscountStatus VARCHAR,         -- 'Used' | 'Unused'
    BillingCurrency VARCHAR NOT NULL,         -- 'USD'
    BillingPeriodStart TIMESTAMP NOT NULL,    -- UTC
    ChargePeriodStart TIMESTAMP NOT NULL,     -- UTC (Mandatory Partition Filter Column)
    ChargePeriodEnd TIMESTAMP NOT NULL,       -- UTC
    ConsumedQuantity DOUBLE DEFAULT 0.0,
    ConsumedUnit VARCHAR,
    BilledCost DOUBLE NOT NULL DEFAULT 0.0,
    EffectiveCost DOUBLE NOT NULL DEFAULT 0.0,
    ListCost DOUBLE NOT NULL DEFAULT 0.0,
    ContractedCost DOUBLE NOT NULL DEFAULT 0.0,
    Tags JSON,                                -- e.g. '{"owner":"payments","env":"prod","cost_center":"CC-10"}'
    PRIMARY KEY (
        client_id, BillingPeriodStart, ChargePeriodStart,
        SubAccountId, ServiceName, COALESCE(ResourceId, ''),
        ChargeCategory, COALESCE(CommitmentDiscountId, ''), COALESCE(CommitmentDiscountStatus, '')
    )
);

CREATE TABLE IF NOT EXISTS tickets_ledger (
    fingerprint VARCHAR PRIMARY KEY,          -- sha256(client_id:capability:sub_account_id:service_name:period)[:16]
    ticket_id VARCHAR NOT NULL UNIQUE,        -- 'FIN-001'
    client_id VARCHAR NOT NULL,
    capability VARCHAR NOT NULL,
    maturity_tier VARCHAR NOT NULL,           -- 'Crawl' | 'Walk' | 'Run'
    allocation_mode VARCHAR NOT NULL,         -- 'Showback' | 'Chargeback' | 'N/A'
    status VARCHAR NOT NULL,                  -- 'PROPOSED' | 'APPROVED' | 'IMPLEMENTED' | 'REJECTED' | 'FALSE_POSITIVE' | 'SNOOZED'
    severity VARCHAR NOT NULL,                -- 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
    sub_account_id VARCHAR NOT NULL,
    service_name VARCHAR NOT NULL,
    period_bucket VARCHAR NOT NULL,           -- '2026-10' or '2026-10-20'
    estimated_monthly_impact_usd DOUBLE NOT NULL,
    billing_currency VARCHAR NOT NULL,
    kpi_name VARCHAR NOT NULL,
    kpi_value DOUBLE NOT NULL,
    title VARCHAR NOT NULL,
    resolution_note VARCHAR DEFAULT '',
    created_at_utc TIMESTAMP NOT NULL,
    updated_at_utc TIMESTAMP NOT NULL
);
```

## 3. Client Profile Schema (`client_profile.yaml`)
```yaml
client_id: "acme-corp"
client_name: "Acme FinTech Corp"
niche: "B2B Payments & Ledger SaaS"
billing_currency: "USD"
timezone: "UTC"
target_maturity: "Walk" # Crawl | Walk | Run
allocation_policy:
  mode: "Chargeback" # Showback | Chargeback
  required_tags: ["owner", "env", "cost_center", "service"]
  shared_cost_sub_accounts: ["shared-network-001", "security-core-002"]
  shared_apportionment_method: "proportional_effective_cost" # proportional_effective_cost | even_split | fixed_pct
budget_policy:
  cycle: "monthly"
  total_monthly_budget_usd: 120000.00
  holdback_pct: 10.0
  sub_account_budgets_usd:
    "prod-payments-101": 65000.00
    "ml-platform-202": 35000.00
    "shared-network-001": 20000.00
commitment_policy:
  max_term_months: 12
  allow_upfront_payment: false
  target_esr_pct: 22.0
```

## 4. Ticket File Schema (`tickets/FIN-XXX.md`)
Written atomically via `.tmp` + `os.replace()` and indexed into HippoRAG `client_<id>_graph`:
```markdown
---
ticket_id: FIN-001
fingerprint: "9f8e7d6c5b4a3210"
client_id: "acme-corp"
capability: "anomaly-management"
maturity_tier: "Walk"
allocation_mode: "Chargeback"
status: "PROPOSED"
severity: "HIGH"
sub_account_id: "ml-platform-202"
service_name: "AmazonEC2"
period_bucket: "2026-10-20"
estimated_monthly_impact_usd: 4200.00
billing_currency: "USD"
kpi_name: "anomaly_unpredicted_variance"
kpi_value: 140.00
created_at_utc: "2026-10-20T12:00:00Z"
updated_at_utc: "2026-10-20T12:00:00Z"
---
# [HIGH] Unpredicted EffectiveCost Spike in ml-platform-202 / AmazonEC2

## Evidence & KPI Formula
- **KPI (`anomaly_unpredicted_variance`)**: `AnomalyEventEffectiveCost - BaselinePredictedEffectiveCost = $140.00/day` (`$4,200.00/month` projected Cost Avoidance).
- **Currency / Timezone**: `USD` / `UTC`.

## FinOps Foundation Guidance (`Walk`)
- **Capability**: `@finops_capabilities_md/capabilities/anomaly-management.md` (https://www.finops.org/framework/capabilities/anomaly-management/)

## Recommended Action
Verify newly launched `p4d` instances lacking `owner` tag; terminate if orphaned or document planned run window.

## Resolution / Client Feedback
_Pending review._
```
