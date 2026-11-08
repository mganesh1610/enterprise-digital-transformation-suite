# Business handoff and acceptance

| Decision question | Asset | Acceptance check | Notes |
| --- | --- | --- | --- |
| Where is signed transaction value concentrated? | gold_monthly_country | Country totals reconcile to silver ledger | Signed transaction value across countries and months |
| Which customer groups merit follow-up analysis? | gold_segment_revenue | Known groups plus unknown bucket reconcile | Deterministic monetary quartile segmentation |
| Are metric definitions consistent? | data_catalog.csv + schema.md | Review grain, currency, credits, unknowns and refresh | Documented lineage, grain, and refresh schedule |
| Can an analyst retrieve a repeatable answer? | ask.py | Display SQL and compare exported aggregates | Governed SQL question templates |

Build order: validate the source/hash and schema; run the financial and key checks; review gold assets against direct totals; inspect the catalog; execute the three governed questions. If moving to Databricks, establish a workspace/catalog/volume and approved credentials, then execute the handoff SQL and repeat reconciliation.

Enablement exercise: compare country totals, inspect the unknown-identity segment, then explain why customer counts cannot be summed across monthly slices. Record feedback about metric definitions before changing code.
