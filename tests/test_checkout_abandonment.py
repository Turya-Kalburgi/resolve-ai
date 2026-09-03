import unittest
from app.database import Base, engine, SessionLocal
from app.models_checkout import CheckoutSession
from app.services.risk_engine import evaluate_checkout_risk
from app.services.recovery_agent import generate_recovery_recommendation
from app.services.policy_engine import evaluate_policy
from app.services.checkout_evaluator import run_checkout_batch_evaluation
from app.services.batch_evaluator import run_batch_evaluation
from app.schemas_risk import RiskCategory
from app.schemas_recovery import RecoveryActionType, RecoveryStrategy
from app.schemas_policy import PolicyDecision

class TestCheckoutAbandonment(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_abandoned_checkout_correctly_identified(self):
        """Test 1: Abandoned checkout is correctly diagnosed with CHECKOUT_ABANDONMENT category."""
        chk = CheckoutSession(
            id="chk_test_01",
            customer_id="cust_chk_1",
            merchant_id="merch_1",
            amount=120.00,
            currency="USD",
            status="ABANDONED",
            payment_attempted=False,
            description="Abandoned Cart #101"
        )
        risk = evaluate_checkout_risk(chk)
        self.assertEqual(risk.category, RiskCategory.CHECKOUT_ABANDONMENT)
        self.assertTrue(risk.is_flagged)

    def test_completed_checkout_not_treated_as_abandonment(self):
        """Test 2: Completed checkout is treated as low risk normal."""
        chk = CheckoutSession(
            id="chk_test_02",
            customer_id="cust_chk_2",
            merchant_id="merch_1",
            amount=150.00,
            currency="USD",
            status="COMPLETED",
            payment_attempted=True,
            description="Completed Checkout"
        )
        risk = evaluate_checkout_risk(chk)
        self.assertEqual(risk.category, RiskCategory.LOW_RISK_NORMAL)
        self.assertFalse(risk.is_flagged)

    def test_started_checkout_not_treated_as_abandonment(self):
        """Test 3: Started checkout is treated as pending settlement / in-progress."""
        chk = CheckoutSession(
            id="chk_test_03",
            customer_id="cust_chk_3",
            merchant_id="merch_1",
            amount=200.00,
            currency="USD",
            status="STARTED",
            payment_attempted=False,
            description="Active Checkout Session"
        )
        risk = evaluate_checkout_risk(chk)
        self.assertEqual(risk.category, RiskCategory.PENDING_SETTLEMENT)
        self.assertFalse(risk.is_flagged)

    def test_recovery_recommendation_evidence_grounded(self):
        """Test 4 & 5: Recovery recommendation uses evidence-grounded reasoning without invented causes."""
        chk = CheckoutSession(
            id="chk_test_04",
            customer_id="cust_chk_4",
            merchant_id="merch_1",
            amount=120.00,
            currency="USD",
            status="ABANDONED",
            payment_attempted=False,
            description="Abandoned Shopping Cart"
        )
        setattr(chk, "retry_count", 0)

        risk = evaluate_checkout_risk(chk)
        rec = generate_recovery_recommendation(risk)

        exp = rec.explanation
        self.assertIn("OBSERVED FACTS: Checkout chk_test_04 is 'abandoned'", exp)
        self.assertIn("INFERENCE: The checkout session ended before a payment attempt was recorded", exp)
        self.assertEqual(rec.recommended_strategy, RecoveryStrategy.CHECKOUT_RECOVERY_NUDGE)
        self.assertEqual(rec.action_type, RecoveryActionType.PROMPT_RETRY)

        # Confirm zero invented causes
        exp_lower = exp.lower()
        self.assertNotIn("insufficient funds", exp_lower)
        self.assertNotIn("expired card", exp_lower)
        self.assertNotIn("gateway error", exp_lower)
        self.assertNotIn("price objection", exp_lower)

    def test_excessive_checkout_reminders_blocked_by_rule_002(self):
        """Test 8: Excessive reminders (retry_count >= 3) are blocked by Policy Engine RULE_002."""
        chk = CheckoutSession(
            id="chk_test_05",
            customer_id="cust_chk_5",
            merchant_id="merch_1",
            amount=350.00,
            currency="USD",
            status="ABANDONED",
            payment_attempted=False,
            description="Abandoned Cart High Value"
        )
        setattr(chk, "retry_count", 3)

        risk = evaluate_checkout_risk(chk)
        rec = generate_recovery_recommendation(risk)
        # Force PROMPT_RETRY action to test policy Rule 002 gate
        rec.action_type = RecoveryActionType.PROMPT_RETRY
        rec.requires_human_escalation = False

        pol = evaluate_policy(chk, rec, retry_count=3)
        self.assertEqual(pol.decision, PolicyDecision.BLOCKED)
        self.assertTrue(any(r.rule_id == "RULE_002" and not r.passed for r in pol.rules_evaluated))

    def test_completed_checkout_cannot_be_recovered(self):
        """Test 10: Completed checkout produces NO_OP and cannot trigger recovery."""
        chk = CheckoutSession(
            id="chk_test_06",
            customer_id="cust_chk_6",
            merchant_id="merch_1",
            amount=150.00,
            currency="USD",
            status="COMPLETED",
            payment_attempted=True,
            description="Completed Order"
        )
        risk = evaluate_checkout_risk(chk)
        rec = generate_recovery_recommendation(risk)
        self.assertEqual(rec.action_type, RecoveryActionType.NO_OP)

    def test_checkout_batch_evaluation_and_isolation(self):
        """Test 11 & 12: Checkout metrics are isolated and 30-payment benchmark remains identical."""
        # 1. Run checkout batch evaluation (6 cases)
        chk_res = run_checkout_batch_evaluation(self.db, reset_db=True)
        self.assertEqual(chk_res["total_checkout_sessions_evaluated"], 6)
        breakdown = chk_res["outcomes_breakdown"]
        self.assertEqual(breakdown["RECOVERED"], 3)
        self.assertEqual(breakdown["FAILED"], 1)
        self.assertEqual(breakdown["BLOCKED"], 1)

        # 2. Run 30-payment benchmark evaluation
        pay_res = run_batch_evaluation(self.db, reset_db=True)
        pay_breakdown = pay_res["outcomes_breakdown"]
        self.assertEqual(pay_res["total_payments_processed"], 30)
        self.assertEqual(pay_breakdown["RECOVERED"], 8)
        self.assertEqual(pay_breakdown["FAILED"], 4)
        self.assertEqual(pay_breakdown["BLOCKED"], 4)
        self.assertEqual(pay_breakdown["ESCALATED"], 6)
        self.assertEqual(pay_breakdown["MONITORING"], 4)
        self.assertEqual(pay_breakdown["NO_ACTION"], 4)

if __name__ == "__main__":
    unittest.main()
