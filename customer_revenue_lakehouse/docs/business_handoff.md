# Business handoff and acceptance

| Decision question | Asset | Acceptance check | Boundary |
| --- | --- | --- | --- |
| Where is signed transaction value concentrated? | gold_monthly_country | Country totals reconcile to silver ledger | Descriptive historical revenue proxy; no profitability or causal claim |
| Which customer groups merit follow-up analysis? | gold_segment_revenue | Known groups plus unknown bucket reconcile | No contact permissions, churn labels or marketing experiment |
| Are metric definitions consistent? | data_catalog.csv + schema.md | Review grain, currency, credits, unknowns and refresh | Local catalog does not enforce enterprise access controls |
| Can an analyst retrieve a repeatable answer? | ask.py | Display SQL and compare exported aggregates | Three exact question templates, not open-ended NL2SQL |

Build order: validate the source/hash and schema; run the financial and key checks; review gold assets against direct totals; inspect the catalog; execute the three training questions. If moving to Databricks, first establish a workspace/catalog/volume and approved credentials, then execute the handoff SQL and repeat reconciliation. No service is provisioned by this module.

Example enablement exercise: compare country totals, inspect the unknown-identity segment, then explain why customer counts cannot be summed across monthly slices. Record feedback about metric definitions before changing code. This is a prepared exercise; no real user training or adoption result is claimed.
