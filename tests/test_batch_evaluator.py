import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

from app.database import Base, get_db
from app.main import app
from app.models import Payment
from app.models_audit import AuditLog
from app.schemas_policy import PolicyDecision
from app.services.risk_engine import evaluate_payment_risk
from app.services.recovery_agent import generate_recovery_recommendation
from app.services.policy_engine import evaluate_policy
from app.services.batch_evaluator import run_batch_evaluation

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_resolve_ai.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

class TestBatchEvaluator(unittest.TestCase):

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

    def test_batch_distribution_is_deterministic(self):
        """Batch evaluation of 30 payments produces exact deterministic outcome distribution."""
        results = run_batch_evaluation(self.db, reset_db=True)
        
        self.assertEqual(results["total_payments_processed"], 30)
        breakdown = results["outcomes_breakdown"]
        
        self.assertEqual(breakdown["RECOVERED"], 8)
        self.assertEqual(breakdown["FAILED"], 4)
        self.assertEqual(breakdown["BLOCKED"], 4)
        self.assertEqual(breakdown["ESCALATED"], 6)  # 4 disputed + 2 low confidence
        self.assertEqual(breakdown["MONITORING"], 4)
        self.assertEqual(breakdown["NO_ACTION"], 4)

    def test_sc07_unrecognized_status_triggers_rule003(self):
        """Unrecognized payment status yields AI confidence < 0.70, naturally triggering Policy RULE_003."""
        p_unknown = Payment(
            id=str(uuid.uuid4()),
            amount=250.0,
            currency="USD",
            status="declined_unknown",
            customer_id="cust_sc07",
            merchant_id="merch_1"
        )
        self.db.add(p_unknown)
        self.db.commit()

        risk = evaluate_payment_risk(p_unknown)
        rec = generate_recovery_recommendation(risk)
        self.assertLess(rec.confidence_score, 0.70)  # Below 0.70 threshold

        policy = evaluate_policy(p_unknown, rec, retry_count=0)
        self.assertEqual(policy.decision, PolicyDecision.ESCALATED)
        
        rule3 = next(r for r in policy.rules_evaluated if r.rule_id == "RULE_003")
        self.assertFalse(rule3.passed)
        self.assertEqual(rule3.severity, "ESCALATE")

    def test_evaluate_batch_api_endpoint(self):
        """POST /payments/evaluate-batch executes synthetic batch and returns summary."""
        res = self.client.post("/payments/evaluate-batch?reset_db=true")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        self.assertEqual(data["total_payments_processed"], 30)
        self.assertIn("outcomes_breakdown", data)
        self.assertEqual(data["outcomes_breakdown"]["RECOVERED"], 8)

if __name__ == "__main__":
    unittest.main()
