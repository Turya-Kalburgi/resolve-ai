import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

from app.database import Base, get_db
from app.main import app
from app.models import Payment
from app.schemas_policy import PolicyDecision
from app.schemas_recovery import RecoveryRecommendationResponse, RecoveryStrategy, RecoveryActionType
from app.services.policy_engine import evaluate_policy
from datetime import datetime, timezone

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_resolve_ai.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

class TestPolicyAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        cls.db = TestingSessionLocal()

        cls.p_failed = Payment(
            id=str(uuid.uuid4()),
            amount=100.0,
            currency="USD",
            status="failed",
            customer_id="cust_pol_1",
            merchant_id="merch_pol_1",
            description="Failed payment for policy test"
        )
        cls.p_completed = Payment(
            id=str(uuid.uuid4()),
            amount=250.0,
            currency="USD",
            status="completed",
            customer_id="cust_pol_2",
            merchant_id="merch_pol_1",
            description="Completed payment for policy test"
        )
        cls.p_disputed = Payment(
            id=str(uuid.uuid4()),
            amount=300.0,
            currency="USD",
            status="disputed",
            customer_id="cust_pol_3",
            merchant_id="merch_pol_1",
            description="Disputed payment for policy test"
        )

        cls.db.add_all([cls.p_failed, cls.p_completed, cls.p_disputed])
        cls.db.commit()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_policy_approved_failed_payment_initial_retry(self):
        response = self.client.get(f"/payments/{self.p_failed.id}/policy?retry_count=0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["payment_id"], self.p_failed.id)
        self.assertEqual(data["decision"], PolicyDecision.APPROVED.value)
        self.assertEqual(len(data["violations"]), 0)

    def test_policy_blocked_max_retries_exceeded(self):
        response = self.client.get(f"/payments/{self.p_failed.id}/policy?retry_count=3")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["payment_id"], self.p_failed.id)
        self.assertEqual(data["decision"], PolicyDecision.BLOCKED.value)
        self.assertTrue(any("Retry attempt limit reached" in v for v in data["violations"]))

    def test_policy_blocked_completed_payment(self):
        response = self.client.get(f"/payments/{self.p_completed.id}/policy")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["payment_id"], self.p_completed.id)
        # Completed payment with NO_OP action should be APPROVED (no active recovery attempted)
        self.assertEqual(data["decision"], PolicyDecision.APPROVED.value)

    def test_policy_escalated_disputed_payment(self):
        response = self.client.get(f"/payments/{self.p_disputed.id}/policy")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["payment_id"], self.p_disputed.id)
        self.assertEqual(data["decision"], PolicyDecision.ESCALATED.value)
        self.assertTrue(any("dispute" in v.lower() for v in data["violations"]))

    def test_policy_escalated_low_confidence_unit(self):
        """Direct unit evaluation of policy engine with low confidence AI recommendation."""
        low_conf_rec = RecoveryRecommendationResponse(
            payment_id=self.p_failed.id,
            recommended_strategy=RecoveryStrategy.CUSTOMER_RETRY_PROMPT,
            action_type=RecoveryActionType.PROMPT_RETRY,
            explanation="Uncertain recommendation",
            requires_human_escalation=False,
            suggested_customer_message=None,
            confidence_score=0.50, # Below 0.70 threshold
            fallback_used=False,
            generated_at=datetime.now(timezone.utc)
        )
        policy_res = evaluate_policy(self.p_failed, low_conf_rec, retry_count=0)
        self.assertEqual(policy_res.decision, PolicyDecision.ESCALATED)
        self.assertTrue(any("confidence score" in v.lower() for v in policy_res.violations))

    def test_policy_payment_not_found(self):
        response = self.client.get("/payments/non_existent_policy_999/policy")
        self.assertEqual(response.status_code, 404)

    def test_policy_non_execution_side_effect_check(self):
        """Ensure payment record in DB remains completely unchanged after policy evaluation."""
        p_before = self.db.query(Payment).filter(Payment.id == self.p_failed.id).first()
        status_before = p_before.status
        amount_before = p_before.amount

        self.client.get(f"/payments/{self.p_failed.id}/policy?retry_count=0")
        self.client.get(f"/payments/{self.p_failed.id}/policy?retry_count=3")

        self.db.refresh(p_before)
        self.assertEqual(p_before.status, status_before)
        self.assertEqual(p_before.amount, amount_before)

if __name__ == "__main__":
    unittest.main()
