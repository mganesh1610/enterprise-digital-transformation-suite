import sqlite3
import unittest
from decimal import Decimal

import pandas as pd
from pipeline import COLUMNS, ask, build_layers, price_to_mills, transform


def fixture():
    return pd.DataFrame([
        ["100","A","Gift",2,"2011-01-01",Decimal("1.255"),12345,"UK"],
        ["C100","A","Gift",-1,"2011-01-02",Decimal("1.255"),12345,"UK"],
        ["101","B","Other",1,"2011-02-01",2.5,None,"UK"],
        ["102","C","Adjustment",1,"2011-02-01",-1.0,12345,"UK"],
        ["100","A","Gift",2,"2011-01-01",Decimal("1.255"),12345,"UK"],
    ],columns=COLUMNS)


class RevenueTests(unittest.TestCase):
    def setUp(self):
        self.norm=transform(fixture()); self.con=sqlite3.connect(":memory:")
        build_layers(self.con,self.norm)

    def tearDown(self):
        self.con.close()

    def test_fractional_penny_preserved(self):
        self.assertEqual(price_to_mills(Decimal("1.255")),1255)
        with self.assertRaises(ValueError): price_to_mills("1.0001")

    def test_negative_price_quarantined(self):
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM quarantine_invoice_lines").fetchone()[0],1)

    def test_credit_and_duplicates_retained(self):
        self.assertEqual(self.con.execute("SELECT SUM(amount_mills) FROM silver_invoice_lines").fetchone()[0],6265)
        self.assertEqual(int(self.norm.duplicate_flag.sum()),2)

    def test_unknown_identity_bucket_preserved(self):
        self.assertEqual(self.con.execute("SELECT net_mills FROM gold_segment_revenue WHERE segment='Unknown identity'").fetchone()[0],2500)

    def test_unsupported_sql_not_executed(self):
        with self.assertRaises(ValueError): ask(self.con,"DROP TABLE silver_invoice_lines")
        self.assertEqual(len(ask(self.con,"revenue by month?")[1]),2)

    def test_schema_drift_fails_closed(self):
        with self.assertRaises(ValueError): transform(fixture().rename(columns={"Quantity":"Qty"}))

    def test_month_boundary_and_repeat_build(self):
        before=ask(self.con,"revenue by month")[1].to_dict("records")
        self.assertEqual(before[0]["net_gbp"],3.765)
        build_layers(self.con,self.norm)
        self.assertEqual(before,ask(self.con,"revenue by month")[1].to_dict("records"))


if __name__ == "__main__": unittest.main(verbosity=2)
