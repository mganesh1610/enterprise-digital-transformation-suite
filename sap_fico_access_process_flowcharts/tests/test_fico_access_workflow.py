#!/usr/bin/env python3
import unittest
from pathlib import Path
from run_fico_access_workflow_audit import run_workflow_audit, OUT_DIR


class TestFicoAccessWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = run_workflow_audit()

    def test_01_event_and_workflow_counts(self):
        self.assertEqual(self.summary["source_event_snapshots"], 141712)
        self.assertEqual(self.summary["consolidated_unique_workflows"], 24918)

    def test_02_consolidation_ratio(self):
        self.assertAlmostEqual(self.summary["reporting_row_consolidation_pct"], 82.42, places=2)

    def test_03_top_categories_exported(self):
        self.assertEqual(self.summary["top_audited_categories"], 12)

    def test_04_integrity_checks_passed(self):
        self.assertEqual(self.summary["access_and_sql_integrity_checks"], "8/8 (100.0%)")

    def test_05_artifacts_exist(self):
        self.assertTrue((OUT_DIR / "process_improvement_summary.csv").exists())
        self.assertTrue((OUT_DIR / "workflow_bottleneck_and_fico_audit.json").exists())


if __name__ == "__main__":
    unittest.main()
