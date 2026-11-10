---
name: finops-capability-lookup
description: Look up the FinOps Foundation definition, maturity model, functional activities and KPIs for any of the 22 FinOps Capabilities. Use when the user asks "what does FinOps say about X", definitions, KPI library lookups, maturity (crawl/walk/run), persona responsibilities, or whenever no other finops-* skill matches the user intent.
---

# FinOps Capability Lookup (Router)

## Capability Knowledge Base
- Canonical path: `finops_capabilities_md/index.md`
- Individual capabilities: `finops_capabilities_md/capabilities/<slug>.md`

## Workflow
1. Classify the task into 1+ FinOps Foundation capability slugs (`data-ingestion`, `allocation`, `anomaly-management`, `forecasting`, `budgeting`, `rate-optimization`, `reporting-analytics`, `automation-tools-services`).
2. Read the corresponding `.md` file to extract:
   - **Definition**
   - **Maturity Assessment (`Crawl / Walk / Run`)**
   - **Measures of Success & KPIs (with exact formulas)**
   - **Official FinOps Foundation URL from `## References`**
3. Combine with the matching stack build skill (`finops-build-*`) when generating or modifying code.
