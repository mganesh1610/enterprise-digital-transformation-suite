# Customer Revenue Lakehouse

An independent public-data module for reusable commercial BI: immutable source landing, bronze invoice lines, validated silver data, and gold revenue/customer metrics. It adds an executed public-data example to this AI-managed showcase repository. Results here apply only to this module; they do not validate older repository claims.

## Executed results

The UCI Online Retail archive supplied **541,909 invoice lines** dated December 2010 through December 2011. The local build promoted **541,907 lines**, quarantined **2 negative-price adjustments**, retained **135,078 unknown-customer lines**, and reconciled **9,769,872.054 GBP** of signed transaction value across **38 countries**. All **15 data/rebuild checks** and **7 unit tests** passed. Exact source hash, totals and check results are in `outputs/validation_report.json`.

This amount is the dataset's signed transaction value under the documented rules, not audited revenue, profit, a causal effect, or a business saving. The incomplete December 2011 window prevents an unqualified month-over-month growth comparison.

## Architecture

```mermaid
flowchart LR
  A[UCI XLSX archive + SHA-256] --> B[Bronze source rows]
  B --> C[Silver validation + signed monetary ledger]
  B --> Q[Quarantine: invalid records]
  C --> D[Gold monthly country metrics]
  C --> E[Gold customer and segment metrics]
  D --> F[CSV outputs + data catalog]
  E --> F
  F --> G[Three approved SQL question templates]
```

The executed engine is **Python/pandas + SQLite**. The bronze/silver/gold organization demonstrates medallion concepts without claiming a Databricks deployment. `databricks_handoff.sql` is an unexecuted Databricks SQL/Delta adapter. The local CSV catalog documents asset owners, grains, lineage, access assumptions and refresh behavior; it is not a deployed Unity Catalog or an enterprise permissions service.

## Reproduce

```bash
cd customer_revenue_lakehouse
python -m pip install -r requirements.txt
python pipeline.py --archive data/online_retail.zip --output outputs
python -m unittest -v test_pipeline.py
python ask.py 'revenue by customer segment'
```

The pipeline downloads the archive if absent. Keep `data/` and the generated SQLite database local. The normalized CSV is a portable handoff input; the compact validation, catalog, question examples and gold aggregates are versioned. A full rebuild replaces tables and verifies identical ordered gold outputs, avoiding append duplicates.

## Analytical contract

- Grain: one source workbook row, with Excel row number as the lineage key. An invoice identifier is not a line-level primary key.
- Money: convert GBP to integer **mills** (0.001 GBP), retaining fractional pennies. `net_mills = SUM(Quantity × price_mills)`. Convert to GBP only for display.
- Positive quantities contribute to gross value; negative quantities contribute signed credits. Cancellation identifiers remain visible. Zero-price rows are retained but excluded from purchase-invoice counts. These definitions are not a refund-matching model.
- Negative prices and missing critical keys/dates are quarantined; their row count remains reconciled with the source. No source rows disappear silently.
- Missing customer identity remains in overall revenue, and appears in an explicit unknown bucket. Known-customer counts do not include unknown identities.
- Identical-looking records are flagged, not automatically deleted: repeated purchases may be legitimate. The result is a source-preserving ledger, not a claim of deduplicated truth.
- Customer segments use deterministic rank by net value with customer ID as a tie-breaker. Top-quartile rank is descriptive, not a trained predictive model or an experiment.
- The approved question router executes three fixed, visible SQL templates. It is deterministic and does not call an LLM or claim Genie-equivalent conversational intelligence.

## Validation and business acceptance

The check suite covers source-row conservation, source-key uniqueness, quarantine conservation, negative-price exclusion, independent Decimal ledger reconciliation, monthly/country and customer/unknown reconciliation, join cardinality, signed value arithmetic, output grain, customer keys, segment coverage, duplicate retention, approved question execution, and repeat-build idempotence.

The unit tests exercise fractional pennies, credits, duplicate-looking records, missing customer identity, negative prices, schema drift, month boundaries, repeated builds and unsupported questions. Expected totals are calculated from fixture inputs rather than copied from production outputs.

For a business handoff, review `docs/business_handoff.md`: decision questions, metric definitions, acceptance criteria, refresh limitations, and a training exercise. No real stakeholder interviews, user adoption, productivity gain, sales lift or production reliability outcome is asserted.

## Sources and licenses

- Primary, executed: [Daqing Chen (2015), Online Retail, UCI](https://archive.ics.uci.edu/dataset/352/online+retail), DOI [10.24432/C5BW33](https://doi.org/10.24432/C5BW33), CC BY 4.0. Direct archive: <https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip>.
- Backup, located but not executed: [Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii), 1,067,371 source rows across two years. It overlaps the primary dataset's history and must not be presented as independent validation. Its original headers require the documented rename adapter.
- Design references: [Databricks medallion layers](https://docs.databricks.com/aws/en/lakehouse/medallion) and [Unity Catalog concepts](https://docs.databricks.com/aws/en/data-governance/unity-catalog/).

Implementation assistance: Codex. All execution artifacts were produced against public data; no employer data, secrets or private identities are included.
