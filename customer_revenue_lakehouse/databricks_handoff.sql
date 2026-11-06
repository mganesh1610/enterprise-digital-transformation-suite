-- Unexecuted Databricks SQL / Delta handoff.
-- Prerequisites: authorized existing workspace, catalog and Unity Catalog volume.
-- Upload outputs/normalized_invoice_lines.csv to the volume. Replace PUBLIC_DATA.
-- This is not local execution evidence, automatic provisioning, or a Genie deployment.

CREATE SCHEMA IF NOT EXISTS PUBLIC_DATA.bronze;
CREATE SCHEMA IF NOT EXISTS PUBLIC_DATA.silver;
CREATE SCHEMA IF NOT EXISTS PUBLIC_DATA.gold;

CREATE OR REPLACE TABLE PUBLIC_DATA.bronze.invoice_lines
USING DELTA AS
SELECT * FROM read_files(
  '/Volumes/PUBLIC_DATA/default/retail/normalized_invoice_lines.csv',
  format => 'csv', header => true, inferSchema => true
);

CREATE OR REPLACE TABLE PUBLIC_DATA.silver.invoice_lines
USING DELTA AS
SELECT CAST(source_row_id AS BIGINT) source_row_id,
  CAST(InvoiceNo AS STRING) invoice_no, CAST(StockCode AS STRING) stock_code,
  CAST(CustomerID AS STRING) customer_id, Country country,
  CAST(InvoiceDate AS TIMESTAMP) invoice_timestamp, month,
  CAST(Quantity AS BIGINT) quantity, CAST(price_mills AS BIGINT) price_mills,
  CAST(amount_mills AS BIGINT) amount_mills,
  CAST(duplicate_flag AS INT) duplicate_flag
FROM PUBLIC_DATA.bronze.invoice_lines WHERE lower(CAST(valid AS STRING))='true';

CREATE OR REPLACE TABLE PUBLIC_DATA.gold.monthly_country
USING DELTA AS
SELECT month,country,COUNT(*) line_count,
  COUNT(DISTINCT CASE WHEN quantity>0 AND price_mills>0 THEN invoice_no END) purchase_invoices,
  COUNT(DISTINCT customer_id) known_customers,
  SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) unknown_customer_lines,
  SUM(CASE WHEN quantity>0 THEN amount_mills ELSE 0 END) gross_mills,
  SUM(CASE WHEN quantity<0 THEN amount_mills ELSE 0 END) credit_mills,
  SUM(amount_mills) net_mills
FROM PUBLIC_DATA.silver.invoice_lines GROUP BY month,country;

COMMENT ON TABLE PUBLIC_DATA.gold.monthly_country IS
 'Public retail data; grain month x country; GBP mills; signed credit handling; unknown identities retained. Static historical source, not a live sales system.';

-- Must return zero after execution before presenting results:
SELECT (SELECT SUM(net_mills) FROM PUBLIC_DATA.gold.monthly_country)
 -(SELECT SUM(amount_mills) FROM PUBLIC_DATA.silver.invoice_lines) reconciliation_delta_mills;
-- Suggested reviewed access policy (not executed): grant SELECT only on gold
-- to an existing analyst group; retain bronze/silver access with data stewards.
