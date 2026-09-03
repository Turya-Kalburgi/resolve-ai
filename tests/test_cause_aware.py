import unittest
from app.models import Payment
from app.services.risk_engine import evaluate_payment_risk
from app.services.recovery_agent import generate_recovery_recommendation
from app.schemas_risk import RiskCategory
from app.schemas_recovery import RecoveryActionType

class TestCauseAwareDiagnosis(unittest.TestCase):

    def test_cause_aware_max_retries_exceeded(self):
        """Verifies failed payment with retry_count >= 3 is diagnosed as max retry limit reached."""
        p = Payment(
            id="p_test_max_retry",
            amount=450.00,
            currency="USD",
            status="failed",
            customer_id="cust_999",
            merchant_id="merch_1",
            description="Hardware Purchase"
        )
        setattr(p, "retry_count", 3)

        risk = evaluate_payment_risk(p)
        self.assertIn("maximum retry limit", risk.reasons[0].lower())

        rec = generate_recovery_recommendation(risk)
        exp_lower = rec.explanation.lower()
        self.assertIn("maximum retry threshold reached", exp_lower)
        self.assertEqual(rec.action_type, RecoveryActionType.HUMAN_REVIEW)
        self.assertTrue(rec.requires_human_escalation)

    def test_cause_aware_subscription_intent(self):
        """Verifies subscription failure uses recurring subscription inference."""
        p = Payment(
            id="p_test_sub",
            amount=150.00,
            currency="USD",
            status="failed",
            customer_id="cust_888",
            merchant_id="merch_1",
            description="SaaS Subscription Renewal"
        )
        setattr(p, "retry_count", 0)

        risk = evaluate_payment_risk(p)
        rec = generate_recovery_recommendation(risk)
        exp_lower = rec.explanation.lower()
        self.assertIn("recurring subscription", exp_lower)
        self.assertEqual(rec.action_type, RecoveryActionType.PROMPT_RETRY)

    def test_ambiguous_status_no_invented_causes(self):
        """Verifies unrecognized status explicitly states cause is ambiguous without inventing facts."""
        p = Payment(
            id="p_test_unk",
            amount=380.00,
            currency="USD",
            status="declined_unknown",
            customer_id="cust_777",
            merchant_id="merch_1",
            description="Unknown Terminal Code"
        )
        setattr(p, "retry_count", 0)

        risk = evaluate_payment_risk(p)
        self.assertEqual(risk.category, RiskCategory.UNKNOWN_STATUS)

        rec = generate_recovery_recommendation(risk)
        exp_lower = rec.explanation.lower()
        self.assertIn("ambiguous", exp_lower)
        self.assertNotIn("insufficient funds", exp_lower)
        self.assertNotIn("expired card", exp_lower)
        self.assertNotIn("bank dispute fine", exp_lower)
        self.assertNotIn("gateway penalty fee", exp_lower)

if __name__ == "__main__":
    unittest.main()
