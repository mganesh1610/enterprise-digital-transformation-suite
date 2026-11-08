# Schema and source mapping

| Source XLSX column | Bronze/silver field | Meaning and handling |
| --- | --- | --- |
| InvoiceNo | InvoiceNo | Text invoice key; prefix C indicates cancellation; not line-unique |
| StockCode | StockCode | Text product key, including nonnumeric codes |
| Description | Description | Nullable source description; no invented imputation |
| Quantity | Quantity | Signed integer units |
| InvoiceDate | InvoiceDate, month | Source local timestamp; month YYYY-MM; no invented timezone |
| UnitPrice | UnitPrice, price_mills | Source decimal text and exact GBP × 1,000 integer |
| CustomerID | CustomerID | Nullable pseudonymous source ID, normalized to text |
| Country | Country | Source country label; unique dimension prevents join multiplication |
| Excel row number | source_row_id | Unique lineage key, starts at 2 |
| Derived | amount_mills | Quantity × price_mills; signed integer |
| Derived | valid, is_cancellation, duplicate_flag | Validation, cancellation and advisory duplicate flags |

`bronze_invoice_lines` retains every source row in a minimally typed staging representation. The original archive is the immutable landing object. `quarantine_invoice_lines` contains failed critical fields or negative prices. `silver_invoice_lines` contains promoted rows with a unique source-row index.

`gold_monthly_country` grain: month × country. Columns: month, Country, line_count, purchase_invoices, known_customers, unknown_customer_lines, gross_mills, credit_mills, net_mills. Distinct counts at this grain are not additive across countries/months.

`gold_customer_metrics` grain: known customer. Columns: CustomerID, net_mills, purchase_invoices, last_purchase, monetary_rank, customer_count, segment. Last purchase ignores credits and zero-price records. `gold_segment_revenue` includes Top quartile, Other known, and Unknown identity. Unknown bucket customer count is unavailable, not zero.

The backup workbook uses original names such as Invoice, Price and Customer ID. Rename them to InvoiceNo, UnitPrice and CustomerID, select one dated worksheet, preserve a source-sheet field and assign a composite sheet/row key before running the same contract. Do not concatenate overlapping histories.
