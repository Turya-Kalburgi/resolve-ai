import unittest
from app.database import Base, engine, SessionLocal
from app.models import Payment
from app.services.risk_engine import evaluate_payment_risk
from app.services.recovery_agent import generate_recovery_recommendation
from app.services.policy_engine import evaluate_policy
from app.services.batch_evaluator import run_batch_evaluation
from app.schemas_recovery import RecoveryActionType, RecoveryStrategy
from app.schemas_policy import PolicyDecision

class TestSubscriptionRecovery(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_failed_subscription_gets_subscription_aware_reasoning(self):
        """Test 1 & 2: Failed subscription gets subscription-aware reasoning and intent in recommendation."""
        p = Payment(
            id="p_sub_01",
            amount=150.00,
            currency="USD",
            status="failed",
            customer_id="cust_sub_101",
            merchant_id="merch_1",
            description="SaaS Subscription Renewal"
        )
        setattr(p, "retry_count", 0)

        risk = evaluate_payment_risk(p)
        rec = generate_recovery_recommendation(risk)

        exp = rec.explanation
        self.assertIn("intent 'RECURRING_SUBSCRIPTION'", exp)
        self.assertIn("Recurring subscription renewal failure detected", exp)
        self.assertEqual(rec.recommended_strategy, RecoveryStrategy.CUSTOMER_RETRY_PROMPT)

    def test_subscription_uses_prompt_retry_action(self):
        """Test 3: Subscription recovery uses existing PROMPT_RETRY action vocabulary."""
        p = Payment(
            id="p_sub_02",
            amount=180.00,
            currency="EUR",
            status="failed",
            customer_id="cust_sub_102",
            merchant_id="merch_1",
            description="Cloud Service Plan Upgrade"
        )
        setattr(p, "retry_count", 0)

        risk = evaluate_payment_risk(p)
        rec = generate_recovery_recommendation(risk)

        self.assertEqual(rec.action_type, RecoveryActionType.PROMPT_RETRY)
        self.assertFalse(rec.requires_human_escalation)

    def test_subscription_max_retries_blocked_by_rule_002(self):
        """Test 4: Subscription with retry_count >= 3 is blocked by RULE_002 when PROMPT_RETRY is attempted."""
        p = Payment(
            id="p_sub_03",
            amount=250.00,
            currency="USD",
            status="failed",
            customer_id="cust_sub_103",
            merchant_id="merch_1",
            description="Enterprise Subscription Renewal"
        )
        setattr(p, "retry_count", 3)

        # 1. Direct Policy Engine validation: PROMPT_RETRY + retry_count >= 3 is BLOCKED by RULE_002
        risk = evaluate_payment_risk(p)
        rec_retry = generate_recovery_recommendation(evaluate_payment_risk(Payment(
            id="p_sub_03_sub", amount=250.0, currency="USD", status="failed", customer_id="c1", merchant_id="m1", description="Subscription Renewal"
        )))
        # Force PROMPT_RETRY recommendation to test Policy Engine Rule 002 gate
        rec_retry.action_type = RecoveryActionType.PROMPT_RETRY
        rec_retry.requires_human_escalation = False
        
        pol = evaluate_policy(p, rec_retry, retry_count=3)
        self.assertEqual(pol.decision, PolicyDecision.BLOCKED)
        self.assertTrue(any(r.rule_id == "RULE_002" and not r.passed for r in pol.rules_evaluated))

        # 2. Risk/AI Agent validation: retry_count >= 3 automatically flags human review
        rec_auto = generate_recovery_recommendation(risk)
        self.assertEqual(rec_auto.action_type, RecoveryActionType.HUMAN_REVIEW)
        self.assertTrue(rec_auto.requires_human_escalation)

    def test_disputed_subscription_handled_as_dispute(self):
        """Test 5: Disputed subscription payment is dominated by dispute handling / human review."""
        p = Payment(
            id="p_sub_04",
            amount=350.00,
            currency="EUR",
            status="disputed",
            customer_id="cust_sub_104",
            merchant_id="merch_1",
            description="Chargeback on Annual Subscription"
        )
        setattr(p, "retry_count", 0)

        risk = evaluate_payment_risk(p)
        rec = generate_recovery_recommendation(risk)

        self.assertEqual(rec.action_type, RecoveryActionType.HUMAN_REVIEW)
        self.assertTrue(rec.requires_human_escalation)

    def test_completed_subscription_produces_no_action(self):
        """Test 6: Completed subscription payment produces NO_ACTION (NO_OP)."""
        p = Payment(
            id="p_sub_05",
            amount=300.00,
            currency="USD",
            status="completed",
            customer_id="cust_sub_105",
            merchant_id="merch_1",
            description="Completed Monthly Subscription"
        )
        setattr(p, "retry_count", 0)

        risk = evaluate_payment_risk(p)
        rec = generate_recovery_recommendation(risk)

        self.assertEqual(rec.action_type, RecoveryActionType.NO_OP)
        self.assertEqual(rec.recommended_strategy, RecoveryStrategy.NO_ACTION_COMPLETED)

    def test_ambiguous_status_with_subscription_desc_cautious(self):
        """Test 7: Ambiguous status with subscription description does NOT force an automatic retry."""
        p = Payment(
            id="p_sub_06",
            amount=290.00,
            currency="EUR",
            status="declined_unknown",
            customer_id="cust_sub_106",
            merchant_id="merch_1",
            description="Unrecognized Code on Subscription Renewal"
        )
        setattr(p, "retry_count", 0)

        risk = evaluate_payment_risk(p)
        rec = generate_recovery_recommendation(risk)

        self.assertEqual(rec.action_type, RecoveryActionType.HUMAN_REVIEW)
        self.assertTrue(rec.confidence_score < 0.70)
        self.assertTrue(rec.requires_human_escalation)

    def test_benchmark_outcomes_remain_identical(self):
        """Test 10: Existing 30-payment benchmark dataset produces identical 8 RECOVERED, 4 FAILED, 4 BLOCKED, 6 ESCALATED, 4 MONITORING, 4 NO_ACTION."""
        res = run_batch_evaluation(self.db, reset_db=True)
        breakdown = res["outcomes_breakdown"]

        self.assertEqual(res["total_payments_processed"], 30)
        self.assertEqual(breakdown["RECOVERED"], 8)
        self.assertEqual(breakdown["FAILED"], 4)
        self.assertEqual(breakdown["BLOCKED"], 4)
        self.assertEqual(breakdown["ESCALATED"], 6)
        self.assertEqual(breakdown["MONITORING"], 4)
        self.assertEqual(breakdown["NO_ACTION"], 4)

if __name__ == "__main__":
    unittest.main()
