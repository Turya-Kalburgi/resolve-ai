import unittest
from app.database import Base, engine, SessionLocal
from app.seed_demo import DEMO_SCENARIO_SPECS, seed_demo_synthetic_payments
from app.services.baseline_evaluator import run_naive_baseline_evaluation
from app.services.batch_evaluator import run_batch_evaluation
from app.services.metrics_service import compute_metrics_summary

class TestBaselineEvaluator(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_baseline_evaluator_dataset_execution(self):
        """Verifies baseline evaluator processes the exact same 30 dataset records dynamically."""
        res = run_naive_baseline_evaluation()
        self.assertEqual(res["total_payments_evaluated"], len(DEMO_SCENARIO_SPECS))
        self.assertEqual(res["total_payments_evaluated"], 30)

        # Baseline blindly attempts retries on failed payments only
        self.assertGreater(res["retries_attempted"], 0)
        self.assertEqual(res["retries_attempted"], 16) # SC-01 (8) + SC-02 (4) + SC-03 (4)
        self.assertEqual(res["max_retry_limit_violations_attempted"], 4) # SC-03 max retry limit

    def test_baseline_currency_segregation(self):
        """Verifies baseline metrics maintain currency segregation (USD, EUR, GBP, CAD)."""
        res = run_naive_baseline_evaluation()
        by_curr = res["by_currency"]
        self.assertIn("USD", by_curr)
        self.assertIn("EUR", by_curr)
        self.assertIn("GBP", by_curr)
        self.assertIn("CAD", by_curr)

        for curr, stats in by_curr.items():
            self.assertIn("total_payments_evaluated", stats)
            self.assertIn("total_revenue_at_risk", stats)
            self.assertIn("retries_attempted", stats)
            self.assertIn("revenue_recovered", stats)

    def test_side_by_side_comparison_structure(self):
        """Verifies compute_metrics_summary includes baseline vs ResolveAI comparison metrics."""
        run_batch_evaluation(self.db, reset_db=True)
        summary = compute_metrics_summary(self.db)
        
        self.assertIsNotNone(summary.baseline_comparison)
        comp = summary.baseline_comparison
        self.assertEqual(comp["total_evaluated"], 30)
        self.assertEqual(comp["baseline_retries_attempted"], 16)
        self.assertEqual(comp["baseline_max_retry_violations_attempted"], 4)

        res_comp = comp["resolveai_comparison"]
        self.assertEqual(res_comp["total_evaluated"], 30)
        self.assertEqual(res_comp["resolveai_blocked_actions"], 4)
        self.assertEqual(res_comp["resolveai_escalated_actions"], 6)
        self.assertEqual(res_comp["max_retry_limit_violations_avoided"], 4)
        self.assertEqual(res_comp["financial_side_effects_in_resolveai"], 0)

if __name__ == "__main__":
    unittest.main()
