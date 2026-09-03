import unittest
import os
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

from app.database import Base, get_db
from app.main import app
from app.models import Payment
from app.schemas_recovery import RecoveryStrategy, RecoveryActionType
from app.services.risk_engine import evaluate_payment_risk
from app.services.recovery_agent import generate_recovery_recommendation

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_resolve_ai.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

class TestRecoveryAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        cls.db = TestingSessionLocal()

        cls.p_disputed = Payment(
            id=str(uuid.uuid4()),
            amount=150.0,
            currency="USD",
            status="disputed",
            customer_id="cust_rec_1",
            merchant_id="merch_rec_1",
            description="Disputed payment for recovery test"
        )
        cls.p_failed = Payment(
            id=str(uuid.uuid4()),
            amount=75.0,
            currency="USD",
            status="failed",
            customer_id="cust_rec_2",
            merchant_id="merch_rec_1",
            description="Failed payment for recovery test"
        )
        cls.p_pending = Payment(
            id=str(uuid.uuid4()),
            amount=50.0,
            currency="USD",
            status="pending",
            customer_id="cust_rec_3",
            merchant_id="merch_rec_1",
            description="Pending payment for recovery test"
        )
        cls.p_completed = Payment(
            id=str(uuid.uuid4()),
            amount=200.0,
            currency="USD",
            status="completed",
            customer_id="cust_rec_4",
            merchant_id="merch_rec_1",
            description="Completed payment for recovery test"
        )

        cls.db.add_all([cls.p_disputed, cls.p_failed, cls.p_pending, cls.p_completed])
        cls.db.commit()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_recovery_disputed_payment(self):
        response = self.client.get(f"/payments/{self.p_disputed.id}/recovery")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["payment_id"], self.p_disputed.id)
        self.assertEqual(data["recommended_strategy"], RecoveryStrategy.HUMAN_DISPUTE_INVESTIGATION.value)
        self.assertEqual(data["action_type"], RecoveryActionType.HUMAN_REVIEW.value)
        self.assertTrue(data["requires_human_escalation"])
        self.assertIn("chargeback", data["explanation"].lower())

    def test_recovery_failed_payment(self):
        response = self.client.get(f"/payments/{self.p_failed.id}/recovery")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["payment_id"], self.p_failed.id)
        self.assertEqual(data["recommended_strategy"], RecoveryStrategy.CUSTOMER_RETRY_PROMPT.value)
        self.assertEqual(data["action_type"], RecoveryActionType.PROMPT_RETRY.value)
        self.assertFalse(data["requires_human_escalation"])
        self.assertIsNotNone(data["suggested_customer_message"])
        self.assertIn("retry", data["explanation"].lower())

    def test_recovery_pending_payment(self):
        response = self.client.get(f"/payments/{self.p_pending.id}/recovery")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["payment_id"], self.p_pending.id)
        self.assertEqual(data["recommended_strategy"], RecoveryStrategy.SETTLEMENT_MONITORING.value)
        self.assertEqual(data["action_type"], RecoveryActionType.STATUS_MONITOR.value)
        self.assertFalse(data["requires_human_escalation"])

    def test_recovery_completed_payment(self):
        response = self.client.get(f"/payments/{self.p_completed.id}/recovery")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["payment_id"], self.p_completed.id)
        self.assertEqual(data["recommended_strategy"], RecoveryStrategy.NO_ACTION_COMPLETED.value)
        self.assertEqual(data["action_type"], RecoveryActionType.NO_OP.value)
        self.assertFalse(data["requires_human_escalation"])

    def test_recovery_payment_not_found(self):
        response = self.client.get("/payments/non_existent_rec_99999/recovery")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("not found", data["detail"].lower())

    def test_recovery_non_execution_side_effect_check(self):
        """Verify database payment object remains completely unmodified after calling recovery endpoint."""
        p_before = self.db.query(Payment).filter(Payment.id == self.p_failed.id).first()
        status_before = p_before.status
        amount_before = p_before.amount

        self.client.get(f"/payments/{self.p_failed.id}/recovery")
        self.client.get(f"/payments/{self.p_failed.id}/recovery")

        self.db.refresh(p_before)
        self.assertEqual(p_before.status, status_before)
        self.assertEqual(p_before.amount, amount_before)

    # ------------------------------------------------------------------
    # ENHANCED MULTI-SIGNAL REASONING ENGINE TESTS
    # ------------------------------------------------------------------

    def test_recovery_subscription_intent_detection(self):
        """Verifies 'SaaS Subscription Renewal' matches RECURRING_SUBSCRIPTION intent."""
        p_sub = Payment(
            id=str(uuid.uuid4()),
            amount=150.0,
            currency="USD",
            status="failed",
            customer_id="cust_sub_1",
            merchant_id="merch_1",
            description="SaaS Subscription Renewal"
        )
        self.db.add(p_sub)
        self.db.commit()

        risk = evaluate_payment_risk(p_sub)
        rec = generate_recovery_recommendation(risk)
        self.assertIn("intent 'RECURRING_SUBSCRIPTION'", rec.explanation)
        self.assertEqual(rec.confidence_score, 0.92)  # 0.90 + 0.02

    def test_recovery_high_value_detection(self):
        """Verifies amount exceeding threshold triggers High-Value Tier and adjustment."""
        p_hv = Payment(
            id=str(uuid.uuid4()),
            amount=450.0,
            currency="USD",
            status="failed",
            customer_id="cust_hv_1",
            merchant_id="merch_1",
            description="Enterprise Tier Monthly Billing"
        )
        self.db.add(p_hv)
        self.db.commit()

        risk = evaluate_payment_risk(p_hv)
        rec = generate_recovery_recommendation(risk)
        self.assertIn("High-Value Tier", rec.explanation)
        # Base 0.90 + Intent 0.03 - HV 0.05 = 0.88
        self.assertEqual(rec.confidence_score, 0.88)

    def test_recovery_currency_aware_value_tier(self):
        """Verifies €260 EUR exceeds EUR threshold (€250) while $260 USD does not exceed USD threshold ($300)."""
        p_eur = Payment(
            id=str(uuid.uuid4()),
            amount=260.0,
            currency="EUR",
            status="failed",
            customer_id="cust_eur",
            merchant_id="merch_1",
            description="E-commerce Checkout Order"
        )
        p_usd = Payment(
            id=str(uuid.uuid4()),
            amount=260.0,
            currency="USD",
            status="failed",
            customer_id="cust_usd",
            merchant_id="merch_1",
            description="E-commerce Checkout Order"
        )
        self.db.add_all([p_eur, p_usd])
        self.db.commit()

        rec_eur = generate_recovery_recommendation(evaluate_payment_risk(p_eur))
        rec_usd = generate_recovery_recommendation(evaluate_payment_risk(p_usd))

        self.assertIn("High-Value Tier", rec_eur.explanation)
        self.assertIn("Standard Tier", rec_usd.explanation)
        # EUR: 0.90 + 0.00 - 0.05 = 0.85; USD: 0.90 + 0.00 + 0.00 = 0.90
        self.assertEqual(rec_eur.confidence_score, 0.85)
        self.assertEqual(rec_usd.confidence_score, 0.90)

    def test_recovery_multi_signal_reasoning(self):
        """Verifies explanation follows strict 3-part format: OBSERVED FACTS, INFERENCE, RECOMMENDATION."""
        risk = evaluate_payment_risk(self.p_failed)
        rec = generate_recovery_recommendation(risk)
        self.assertIn("OBSERVED FACTS:", rec.explanation)
        self.assertIn("INFERENCE:", rec.explanation)
        self.assertIn("RECOMMENDATION:", rec.explanation)

    def test_recovery_exact_confidence_calculation(self):
        """Verifies exact formula output (Worked Example 1 & 2)."""
        p_ex1 = Payment(
            id=str(uuid.uuid4()),
            amount=150.0,
            currency="USD",
            status="failed",
            customer_id="c1",
            merchant_id="m1",
            description="SaaS Subscription Renewal"
        )
        p_ex2 = Payment(
            id=str(uuid.uuid4()),
            amount=310.0,
            currency="EUR",
            status="failed",
            customer_id="c2",
            merchant_id="m1",
            description="Enterprise Tier Monthly Billing"
        )
        self.db.add_all([p_ex1, p_ex2])
        self.db.commit()

        r1 = generate_recovery_recommendation(evaluate_payment_risk(p_ex1))
        r2 = generate_recovery_recommendation(evaluate_payment_risk(p_ex2))

        self.assertEqual(r1.confidence_score, 0.92)  # Worked example 1
        self.assertEqual(r2.confidence_score, 0.88)  # Worked example 2

    def test_recovery_low_confidence_escalation(self):
        """Ambiguous payment status yields confidence 0.55 (< 0.70 threshold)."""
        p_unk = Payment(
            id=str(uuid.uuid4()),
            amount=380.0,
            currency="USD",
            status="declined_unknown",
            customer_id="c3",
            merchant_id="m1",
            description="Ambiguous Error Response Code"
        )
        self.db.add(p_unk)
        self.db.commit()

        rec = generate_recovery_recommendation(evaluate_payment_risk(p_unk))
        # 0.70 (base) - 0.05 (unknown intent) - 0.05 (HV > 300) - 0.05 (ambiguity) = 0.55
        self.assertEqual(rec.confidence_score, 0.55)

    def test_recovery_no_invented_facts(self):
        """Verifies explanation contains zero unverified phrases like 'insufficient funds', 'card expired', or 'chargeback' for failed payments."""
        risk = evaluate_payment_risk(self.p_failed)
        rec = generate_recovery_recommendation(risk)
        exp_lower = rec.explanation.lower()
        self.assertNotIn("insufficient funds", exp_lower)
        self.assertNotIn("card expired", exp_lower)
        self.assertNotIn("decline code", exp_lower)
        self.assertNotIn("customer history", exp_lower)
        self.assertNotIn("chargeback", exp_lower)

    def test_recovery_deterministic_fallback(self):
        """Verify multi-signal engine produces bit-exact decision fields across multiple invocations (excluding generated_at)."""
        risk = evaluate_payment_risk(self.p_failed)
        rec1 = generate_recovery_recommendation(risk)
        rec2 = generate_recovery_recommendation(risk)

        self.assertEqual(rec1.recommended_strategy, rec2.recommended_strategy)
        self.assertEqual(rec1.action_type, rec2.action_type)
        self.assertEqual(rec1.explanation, rec2.explanation)
        self.assertEqual(rec1.requires_human_escalation, rec2.requires_human_escalation)
        self.assertEqual(rec1.suggested_customer_message, rec2.suggested_customer_message)
        self.assertEqual(rec1.confidence_score, rec2.confidence_score)
        self.assertEqual(rec1.fallback_used, rec2.fallback_used)

    @patch.dict(os.environ, {"LLM_PROVIDER": "none"})
    def test_recovery_unavailable_llm_fallback(self):
        """LLM_PROVIDER=none safely triggers multi-signal deterministic engine."""
        risk = evaluate_payment_risk(self.p_failed)
        rec = generate_recovery_recommendation(risk)
        self.assertTrue(rec.fallback_used)

    @patch.dict(os.environ, {"LLM_PROVIDER": "openai", "LLM_API_KEY": "fake_key"})
    @patch("httpx.Client.post")
    def test_recovery_malformed_llm_response_fallback(self, mock_post):
        """Malformed JSON from LLM safely triggers deterministic fallback engine."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Invalid non-JSON response string"}}]
        }
        mock_post.return_value = mock_resp

        risk = evaluate_payment_risk(self.p_failed)
        rec = generate_recovery_recommendation(risk)
        self.assertTrue(rec.fallback_used)

if __name__ == "__main__":
    unittest.main()
