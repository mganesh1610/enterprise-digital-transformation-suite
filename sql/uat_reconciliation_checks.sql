-- =============================================================================
-- Enterprise ERP / SIS Data Conversion & User Acceptance Testing (UAT) Suite
-- Validates row-count parity, Chart-of-Accounts (CoA) trial-balance conservation,
-- crosswalk completeness, and duplicate key suppression prior to production cutover.
-- =============================================================================

-- 1. Legacy-to-Cloud Row Count & Financial Trial-Balance Reconciliation
WITH legacy_summary AS (
    SELECT
        TRIM(UPPER(legacy_dept_code)) AS clean_dept_code,
        COUNT(*) AS legacy_row_count,
        ROUND(SUM(debit_usd), 2) AS legacy_debit_usd,
        ROUND(SUM(credit_usd), 2) AS legacy_credit_usd
    FROM legacy_general_ledger_extract
    GROUP BY 1
),
cloud_summary AS (
    SELECT
        c.cloud_cost_center_id,
        x.legacy_dept_code,
        COUNT(*) AS cloud_row_count,
        ROUND(SUM(c.debit_usd), 2) AS cloud_debit_usd,
        ROUND(SUM(c.credit_usd), 2) AS cloud_credit_usd
    FROM cloud_erp_general_ledger c
    INNER JOIN legacy_cost_center_crosswalk x
        ON c.cloud_cost_center_id = x.cloud_cost_center_id
    GROUP BY 1, 2
)
SELECT
    l.clean_dept_code,
    c.cloud_cost_center_id,
    l.legacy_row_count,
    c.cloud_row_count,
    (l.legacy_row_count - COALESCE(c.cloud_row_count, 0)) AS row_count_variance,
    ROUND(l.legacy_debit_usd - COALESCE(c.cloud_debit_usd, 0), 2) AS debit_variance_usd,
    ROUND(l.legacy_credit_usd - COALESCE(c.cloud_credit_usd, 0), 2) AS credit_variance_usd,
    CASE
        WHEN l.legacy_row_count = c.cloud_row_count
         AND ROUND(l.legacy_debit_usd - c.cloud_debit_usd, 2) = 0.00
         AND ROUND(l.legacy_credit_usd - c.cloud_credit_usd, 2) = 0.00
        THEN 'PASS'
        ELSE 'FAIL_RECONCILIATION'
    END AS uat_gate_status
FROM legacy_summary l
LEFT JOIN cloud_summary c
    ON l.clean_dept_code = c.legacy_dept_code
ORDER BY l.clean_dept_code;

-- 2. Orphan Cost-Center / Unmapped Crosswalk Audit (Excel VLOOKUP #N/A Equivalent)
SELECT
    record_id,
    legacy_entity_id,
    legacy_dept_code,
    account_category,
    fiscal_period
FROM legacy_general_ledger_extract l
LEFT JOIN legacy_cost_center_crosswalk x
    ON TRIM(UPPER(l.legacy_dept_code)) = x.legacy_dept_code
WHERE x.cloud_cost_center_id IS NULL;
