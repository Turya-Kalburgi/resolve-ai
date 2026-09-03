import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

from app.database import Base, get_db
from app.main import app
from app.models import Payment
from app.models_audit import AuditLog

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_resolve_ai.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

class TestMetricsAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.db = TestingSessionLocal()
        self.db.query(AuditLog).delete()
        self.db.query(Payment).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)

    def test_metrics_scope_excludes_unprocessed_payments(self):
        """Metrics must evaluate strictly payments that have audit records in ResolveAI."""
        p_usd = Payment(
            id=str(uuid.uuid4()),
            amount=150.0,
            currency="USD",
            status="failed",
            customer_id="cust_m1",
            merchant_id="merch_m1",
            description="USD Failed payment"
        )
        p_unprocessed = Payment(
            id=str(uuid.uuid4()),
            amount=500.0,
            currency="USD",
            status="failed",
            customer_id="cust_m3",
            merchant_id="merch_m1",
            description="Unprocessed payment"
        )
        self.db.add_all([p_usd, p_unprocessed])
        self.db.commit()

        # Execute workflow on p_usd only
        res_wf = self.client.post(f"/payments/{p_usd.id}/execute-recovery?retry_count=0&simulate_success=true")
        self.assertEqual(res_wf.status_code, 200)

        # Get metrics summary
        res_m = self.client.get("/metrics/summary")
        self.assertEqual(res_m.status_code, 200)
        data = res_m.json()

        # Only p_usd has been evaluated (p_unprocessed is excluded)
        self.assertEqual(data["overall_payments_evaluated"], 1)
        self.assertIn("USD", data["by_currency"])
        usd_metrics = data["by_currency"]["USD"]
        self.assertEqual(usd_metrics["total_payments_evaluated"], 1)
        self.assertEqual(usd_metrics["total_revenue_at_risk"], 150.0)
        self.assertEqual(usd_metrics["total_revenue_recovered"], 150.0)

    def test_metrics_deduplication_double_counting_prevention(self):
        """Executing workflow multiple times on the same payment ID does NOT duplicate recovered revenue."""
        p_eur = Payment(
            id=str(uuid.uuid4()),
            amount=200.0,
            currency="EUR",
            status="failed",
            customer_id="cust_m2",
            merchant_id="merch_m1",
            description="EUR Failed payment"
        )
        self.db.add(p_eur)
        self.db.commit()

        # Execute workflow on p_eur multiple times
        self.client.post(f"/payments/{p_eur.id}/execute-recovery?retry_count=0&simulate_success=true")
        self.client.post(f"/payments/{p_eur.id}/execute-recovery?retry_count=0&simulate_success=true")

        res_m = self.client.get("/metrics/summary")
        self.assertEqual(res_m.status_code, 200)
        data = res_m.json()

        self.assertIn("EUR", data["by_currency"])
        eur_metrics = data["by_currency"]["EUR"]
        self.assertEqual(eur_metrics["total_payments_evaluated"], 1)
        self.assertEqual(eur_metrics["total_revenue_recovered"], 200.0)  # Counted once, NOT 400.0

    def test_metrics_currency_segregation(self):
        """Metrics are segregated by currency code without raw cross-currency addition."""
        p_usd = Payment(
            id=str(uuid.uuid4()),
            amount=100.0,
            currency="USD",
            status="failed",
            customer_id="cust_m1",
            merchant_id="merch_m1"
        )
        p_eur = Payment(
            id=str(uuid.uuid4()),
            amount=250.0,
            currency="EUR",
            status="failed",
            customer_id="cust_m2",
            merchant_id="merch_m1"
        )
        self.db.add_all([p_usd, p_eur])
        self.db.commit()

        self.client.post(f"/payments/{p_usd.id}/execute-recovery?retry_count=0&simulate_success=true")
        self.client.post(f"/payments/{p_eur.id}/execute-recovery?retry_count=0&simulate_success=true")

        res_m = self.client.get("/metrics/summary")
        self.assertEqual(res_m.status_code, 200)
        data = res_m.json()

        self.assertIn("USD", data["by_currency"])
        self.assertIn("EUR", data["by_currency"])
        self.assertEqual(data["by_currency"]["USD"]["total_revenue_recovered"], 100.0)
        self.assertEqual(data["by_currency"]["EUR"]["total_revenue_recovered"], 250.0)

    def test_audit_trail_preserves_complete_decision_chain(self):
        """Audit trail records preserve complete decision chain across Risk, AI Agent, Policy, and Workflow."""
        p_usd = Payment(
            id=str(uuid.uuid4()),
            amount=175.0,
            currency="USD",
            status="failed",
            customer_id="cust_m1",
            merchant_id="merch_m1"
        )
        self.db.add(p_usd)
        self.db.commit()

        self.client.post(f"/payments/{p_usd.id}/execute-recovery?retry_count=0&simulate_success=true")

        res_audit = self.client.get(f"/audit/logs/{p_usd.id}")
        self.assertEqual(res_audit.status_code, 200)
        data = res_audit.json()
        self.assertGreaterEqual(data["total"], 1)

        entry = data["logs"][0]
        self.assertEqual(entry["payment_id"], p_usd.id)
        self.assertEqual(entry["risk_level"], "HIGH")
        self.assertIn("action_type", entry)
        self.assertEqual(entry["policy_decision"], "APPROVED")
        self.assertEqual(entry["workflow_outcome"], "RECOVERED")
        self.assertTrue(len(entry["execution_logs"]) > 0)
        self.assertTrue(len(entry["policy_rules_evaluated"]) > 0)

    def test_audit_log_not_found(self):
        """Requesting audit logs for non-existent or un-evaluated payment ID returns 404."""
        res_audit = self.client.get("/audit/logs/non_existent_audit_999")
        self.assertEqual(res_audit.status_code, 404)

if __name__ == "__main__":
    unittest.main()
