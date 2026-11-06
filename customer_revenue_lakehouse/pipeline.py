"""Public retail revenue medallion reference implementation. No customer deployment claims."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import urllib.request
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd

SOURCE = "https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip"
SOURCE_PAGE = "https://archive.ics.uci.edu/dataset/352/online+retail"
BACKUP = "https://archive.ics.uci.edu/dataset/502/online+retail+ii"
COLUMNS = ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]


def price_to_mills(value):
    """Preserve original GBP precision, including prices with three decimal places."""
    if pd.isna(value):
        return None
    amount = Decimal(str(value)) * 1000
    if not amount.is_finite() or amount != amount.to_integral_value():
        raise ValueError(f"Price has unsupported precision: {value}")
    return int(amount)


def transform(raw: pd.DataFrame) -> pd.DataFrame:
    if list(raw.columns) != COLUMNS:
        raise ValueError(f"Schema mismatch: expected {COLUMNS}, got {list(raw.columns)}")
    out = raw.copy()
    out.insert(0, "source_row_id", range(2, len(out) + 2))  # Excel header is row 1
    for col in ["InvoiceNo", "StockCode", "Description", "Country"]:
        out[col] = out[col].map(lambda x: str(x).strip() if pd.notna(x) else None)
    out["CustomerID"] = out["CustomerID"].map(lambda x: str(int(x)) if pd.notna(x) else None)
    out["InvoiceDate"] = pd.to_datetime(out["InvoiceDate"], errors="coerce")
    out["price_mills"] = out["UnitPrice"].map(price_to_mills).astype("Int64")
    out["UnitPrice"] = out["UnitPrice"].map(lambda x: str(x) if pd.notna(x) else None)
    out["Quantity"] = pd.to_numeric(out["Quantity"], errors="coerce")
    out["valid"] = (
        out["InvoiceNo"].notna() & out["StockCode"].notna()
        & out["Country"].notna() & out["InvoiceDate"].notna()
        & out["Quantity"].notna() & (out["Quantity"] % 1 == 0)
        & out["price_mills"].notna() & (out["price_mills"] >= 0)
    )
    out["amount_mills"] = (out["Quantity"] * out["price_mills"]).astype("Int64")
    out["is_cancellation"] = out["InvoiceNo"].fillna("").str.upper().str.startswith("C").astype(int)
    out["month"] = out["InvoiceDate"].dt.strftime("%Y-%m")
    out["duplicate_flag"] = raw.duplicated(keep=False).astype(int)
    out["InvoiceDate"] = out["InvoiceDate"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return out


def build_layers(con: sqlite3.Connection, normalized: pd.DataFrame):
    normalized.to_sql("bronze_invoice_lines", con, if_exists="replace", index=False)
    con.executescript("""
    DROP TABLE IF EXISTS silver_invoice_lines;
    CREATE TABLE silver_invoice_lines AS SELECT * FROM bronze_invoice_lines WHERE valid=1;
    CREATE UNIQUE INDEX silver_source_key ON silver_invoice_lines(source_row_id);
    DROP TABLE IF EXISTS quarantine_invoice_lines;
    CREATE TABLE quarantine_invoice_lines AS SELECT * FROM bronze_invoice_lines WHERE valid=0;
    DROP TABLE IF EXISTS dim_country;
    CREATE TABLE dim_country AS SELECT DISTINCT Country FROM silver_invoice_lines;
    CREATE UNIQUE INDEX country_key ON dim_country(Country);
    DROP TABLE IF EXISTS gold_monthly_country;
    CREATE TABLE gold_monthly_country AS
    SELECT s.month, s.Country, COUNT(*) AS line_count,
      COUNT(DISTINCT CASE WHEN s.Quantity>0 AND s.price_mills>0 THEN s.InvoiceNo END) AS purchase_invoices,
      COUNT(DISTINCT s.CustomerID) AS known_customers,
      SUM(CASE WHEN s.CustomerID IS NULL THEN 1 ELSE 0 END) AS unknown_customer_lines,
      SUM(CASE WHEN s.Quantity>0 THEN s.amount_mills ELSE 0 END) AS gross_mills,
      SUM(CASE WHEN s.Quantity<0 THEN s.amount_mills ELSE 0 END) AS credit_mills,
      SUM(s.amount_mills) AS net_mills
    FROM silver_invoice_lines s JOIN dim_country c ON s.Country=c.Country
    GROUP BY s.month,s.Country;
    DROP TABLE IF EXISTS gold_customer_metrics;
    CREATE TABLE gold_customer_metrics AS
    WITH customer AS (
      SELECT CustomerID, SUM(amount_mills) net_mills,
        COUNT(DISTINCT CASE WHEN Quantity>0 AND price_mills>0 THEN InvoiceNo END) purchase_invoices,
        MAX(CASE WHEN Quantity>0 AND price_mills>0 THEN InvoiceDate END) last_purchase
      FROM silver_invoice_lines WHERE CustomerID IS NOT NULL GROUP BY CustomerID
    ), ranked AS (
      SELECT *, ROW_NUMBER() OVER (ORDER BY net_mills DESC, CustomerID) monetary_rank,
        COUNT(*) OVER () customer_count FROM customer
    )
    SELECT *, CASE WHEN monetary_rank <= (customer_count+3)/4 THEN 'Top quartile' ELSE 'Other known' END segment
    FROM ranked;
    DROP VIEW IF EXISTS gold_segment_revenue;
    CREATE VIEW gold_segment_revenue AS
      SELECT segment, COUNT(*) customer_count, SUM(net_mills) net_mills
      FROM gold_customer_metrics GROUP BY segment
      UNION ALL
      SELECT 'Unknown identity',NULL,SUM(amount_mills) FROM silver_invoice_lines WHERE CustomerID IS NULL;
    """)
    con.commit()


QUESTIONS = {
    "revenue by month": "SELECT month,SUM(net_mills)/1000.0 net_gbp FROM gold_monthly_country GROUP BY month ORDER BY month",
    "revenue by country": "SELECT Country,SUM(net_mills)/1000.0 net_gbp FROM gold_monthly_country GROUP BY Country ORDER BY net_gbp DESC",
    "revenue by customer segment": "SELECT segment,customer_count,net_mills/1000.0 net_gbp FROM gold_segment_revenue ORDER BY net_gbp DESC",
}


def ask(con, question: str):
    key = question.lower().strip().rstrip("?")
    if key not in QUESTIONS:
        raise ValueError("Unsupported question. Choose: " + "; ".join(QUESTIONS))
    sql = QUESTIONS[key]
    return sql, pd.read_sql_query(sql, con)


def validate(con, raw, norm):
    result = []
    scalar = lambda sql: con.execute(sql).fetchone()[0]

    def check(name, observed, expected):
        passed = observed == expected
        result.append({"check": name, "observed": observed, "expected": expected, "passed": passed})

    check("bronze source-row conservation", scalar("SELECT COUNT(*) FROM bronze_invoice_lines"), len(raw))
    check("source identifier uniqueness", scalar("SELECT COUNT(DISTINCT source_row_id) FROM bronze_invoice_lines"), len(raw))
    check("silver plus quarantine conservation", scalar("SELECT (SELECT COUNT(*) FROM silver_invoice_lines)+(SELECT COUNT(*) FROM quarantine_invoice_lines)"), len(raw))
    check("negative prices never promoted", scalar("SELECT COUNT(*) FROM silver_invoice_lines WHERE price_mills<0"), 0)
    independent = sum(int(row.Quantity) * price_to_mills(row.UnitPrice)
                      for row in raw.itertuples(index=False) if pd.notna(row.UnitPrice) and row.UnitPrice >= 0
                      and pd.notna(row.InvoiceDate) and pd.notna(row.InvoiceNo) and pd.notna(row.StockCode)
                      and pd.notna(row.Country) and pd.notna(row.Quantity) and row.Quantity % 1 == 0)
    net = scalar("SELECT SUM(amount_mills) FROM silver_invoice_lines") or 0
    check("independent Decimal ledger reconciliation", int(net), independent)
    check("monthly-country net reconciliation", scalar("SELECT SUM(net_mills) FROM gold_monthly_country"), net)
    check("customer plus unknown reconciliation", scalar("SELECT SUM(net_mills) FROM gold_segment_revenue"), net)
    check("country join preserves rows", scalar("SELECT COUNT(*) FROM silver_invoice_lines s JOIN dim_country d ON s.Country=d.Country"), scalar("SELECT COUNT(*) FROM silver_invoice_lines"))
    check("gross plus credits equals net", scalar("SELECT SUM(gross_mills+credit_mills-net_mills) FROM gold_monthly_country"), 0)
    check("monthly-country grain uniqueness", scalar("SELECT COUNT(*) FROM (SELECT month,Country,COUNT(*) n FROM gold_monthly_country GROUP BY month,Country HAVING n>1)"), 0)
    check("known customer primary key", scalar("SELECT COUNT(*)-COUNT(DISTINCT CustomerID) FROM gold_customer_metrics"), 0)
    check("customer segment assignment complete", scalar("SELECT COUNT(*) FROM gold_customer_metrics WHERE segment IS NULL"), 0)
    check("duplicate flagged rows retained", scalar("SELECT COUNT(*) FROM bronze_invoice_lines WHERE duplicate_flag=1"), int(norm.duplicate_flag.sum()))
    check("all three governed question templates execute", sum(len(ask(con,q)[1])>0 for q in QUESTIONS), 3)
    if not all(r["passed"] for r in result):
        raise ValueError(json.dumps(result, indent=2, default=int))
    return result


def run(archive: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(SOURCE, archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as z:
        member = next(n for n in z.namelist() if n.endswith(".xlsx"))
        with z.open(member) as source:
            raw = pd.read_excel(source, engine="openpyxl")
    print(f"Read {len(raw):,} source lines", flush=True)
    norm = transform(raw)
    con = sqlite3.connect(output / "revenue.sqlite")
    build_layers(con, norm)
    checks = validate(con, raw, norm)
    # Re-run from the same normalized input, and compare all ordered gold output bytes.
    before = pd.read_sql_query("SELECT * FROM gold_monthly_country ORDER BY month,Country", con).to_csv(index=False)
    build_layers(con, norm)
    after = pd.read_sql_query("SELECT * FROM gold_monthly_country ORDER BY month,Country", con).to_csv(index=False)
    checks.append({"check": "repeat build is idempotent", "observed": before == after, "expected": True, "passed": before == after})
    if not checks[-1]["passed"]:
        raise ValueError("Non-idempotent rebuild")
    scalar = lambda sql: con.execute(sql).fetchone()[0]
    metrics = {
        "source_rows":len(raw),"silver_rows":scalar("SELECT COUNT(*) FROM silver_invoice_lines"),
        "quarantine_rows":scalar("SELECT COUNT(*) FROM quarantine_invoice_lines"),
        "countries":scalar("SELECT COUNT(*) FROM dim_country"),
        "known_customers":scalar("SELECT COUNT(*) FROM gold_customer_metrics"),
        "unknown_customer_rows":scalar("SELECT COUNT(*) FROM silver_invoice_lines WHERE CustomerID IS NULL"),
        "duplicate_flagged_rows":int(norm.duplicate_flag.sum()),
        "net_mills":scalar("SELECT SUM(amount_mills) FROM silver_invoice_lines"),
        "date_min":str(raw.InvoiceDate.min()),"date_max":str(raw.InvoiceDate.max()),
        "checks_passed":sum(r["passed"] for r in checks),"checks_total":len(checks),
    }
    for name in ["gold_monthly_country", "gold_customer_metrics", "gold_segment_revenue"]:
        pd.read_sql_query(f"SELECT * FROM {name}", con).to_csv(output / f"{name}.csv", index=False)
    # Open data export supports the documented Databricks adapter; it is not committed.
    norm.to_csv(output / "normalized_invoice_lines.csv", index=False)
    catalog = [
        {"asset":n,"layer":l,"grain":g,"upstream":u,"owner":"portfolio maintainer","refresh":"on demand; static 2010-2011 source","access":"local reference; no enterprise RBAC enforcement","classification":"public pseudonymous transactions"}
        for n,l,g,u in [
            ("bronze_invoice_lines","bronze","source workbook row","UCI archive SHA-256"),
            ("silver_invoice_lines","silver","validated source row","bronze_invoice_lines"),
            ("gold_monthly_country","gold","month x country","silver_invoice_lines + dim_country"),
            ("gold_customer_metrics","gold","known customer","silver_invoice_lines"),
            ("gold_segment_revenue","gold","customer segment including unknown bucket","gold_customer_metrics + silver_invoice_lines"),
        ]
    ]
    pd.DataFrame(catalog).to_csv(output / "data_catalog.csv", index=False)
    report={"metrics":metrics,"checks":checks,"provenance":{"source_page":SOURCE_PAGE,"download":SOURCE,
        "archive_sha256":digest,"workbook":member,"backup_located_not_executed":BACKUP,
        "created_utc":datetime.now(timezone.utc).isoformat(),"license":"CC BY 4.0; Daqing Chen (2015), UCI, DOI 10.24432/C5BW33"},
        "boundary":"Executed locally in SQLite, not Databricks, Unity Catalog, Genie, Tableau or Power BI. No business savings or production adoption measured. Backup overlaps source history and is not independent validation."}
    (output/"validation_report.json").write_text(json.dumps(report,indent=2,default=int)+"\n")
    (output/"question_examples.json").write_text(json.dumps({q:{"sql":ask(con,q)[0],"rows":ask(con,q)[1].to_dict("records")} for q in QUESTIONS},indent=2)+"\n")
    con.close()
    print(json.dumps(metrics,indent=2),flush=True)
    return report


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--archive",type=Path,default=Path("data/online_retail.zip"))
    parser.add_argument("--output",type=Path,default=Path("outputs"))
    args=parser.parse_args()
    run(args.archive,args.output)
