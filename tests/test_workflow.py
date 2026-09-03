import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

from app.database import Base, get_db
from app.main import app
from app.models import Payment
from app.schemas_workflow import WorkflowOutcome

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_resolve_ai.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

class TestWorkflowAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        cls.db = TestingSessionLocal()

        cls.p_failed = Payment(
            id=str(uuid.uuid4()),
            amount=120.0,
            currency="USD",
            status="failed",
            customer_id="cust_wf_1",
            merchant_id="merch_wf_1",
            description="Failed payment for workflow test"
        )
        cls.p_pending = Payment(
            id=str(uuid.uuid4()),
            amount=85.0,
            currency="USD",
            status="pending",
            customer_id="cust_wf_2",
            merchant_id="merch_wf_1",
            description="Pending payment for workflow test"
        )
        cls.p_completed = Payment(
            id=str(uuid.uuid4()),
            amount=300.0,
            currency="USD",
            status="completed",
            customer_id="cust_wf_3",
            merchant_id="merch_wf_1",
            description="Completed payment for workflow test"
        )
        cls.p_disputed = Payment(
            id=str(uuid.uuid4()),
            amount=450.0,
            currency="USD",
            status="disputed",
            customer_id="cust_wf_4",
            merchant_id="merch_wf_1",
            description="Disputed payment for workflow test"
        )

        cls.db.add_all([cls.p_failed, cls.p_pending, cls.p_completed, cls.p_disputed])
        cls.db.commit()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_approved_prompt_retry_success(self):
        """Active simulated recovery (PROMPT_RETRY with simulate_success=True) produces RECOVERED outcome."""
        response = self.client.post(f"/payments/{self.p_failed.id}/execute-recovery?retry_count=0&simulate_success=true")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["payment_id"], self.p_failed.id)
        self.assertEqual(data["outcome"], WorkflowOutcome.RECOVERED.value)
        self.assertEqual(data["policy_decision"], "APPROVED")
        self.assertEqual(data["recovered_amount"], 120.0)
        self.assertEqual(data["new_payment_status"], "completed")

        # Verify DB state was updated
        db_payment = self.db.query(Payment).filter(Payment.id == self.p_failed.id).first()
        self.db.refresh(db_payment)
        self.assertEqual(db_payment.status, "completed")

    def test_approved_prompt_retry_failure(self):
        """Failed simulated recovery (PROMPT_RETRY with simulate_success=False) produces FAILED outcome."""
        # Create a fresh failed payment for failure test
        p_failed_2 = Payment(
            id=str(uuid.uuid4()),
            amount=90.0,
            currency="USD",
            status="failed",
            customer_id="cust_wf_5",
            merchant_id="merch_wf_1",
            description="Failed payment 2"
        )
        self.db.add(p_failed_2)
        self.db.commit()

        response = self.client.post(f"/payments/{p_failed_2.id}/execute-recovery?retry_count=0&simulate_success=false")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["outcome"], WorkflowOutcome.FAILED.value)
        self.assertEqual(data["policy_decision"], "APPROVED")
        self.assertEqual(data["recovered_amount"], 0.0)
        self.assertEqual(data["new_payment_status"], "failed")

    def test_approved_status_monitor(self):
        """STATUS_MONITOR action produces MONITORING outcome with zero recovered revenue."""
        response = self.client.post(f"/payments/{self.p_pending.id}/execute-recovery")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["outcome"], WorkflowOutcome.MONITORING.value)
        self.assertEqual(data["policy_decision"], "APPROVED")
        self.assertEqual(data["recovered_amount"], 0.0)
        self.assertEqual(data["new_payment_status"], "pending")

    def test_approved_no_op(self):
        """NO_OP action for completed payment produces NO_ACTION outcome with zero additional revenue."""
        response = self.client.post(f"/payments/{self.p_completed.id}/execute-recovery")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["outcome"], WorkflowOutcome.NO_ACTION.value)
        self.assertEqual(data["policy_decision"], "APPROVED")
        self.assertEqual(data["recovered_amount"], 0.0)
        self.assertEqual(data["new_payment_status"], "completed")

    def test_blocked_max_retries_exceeded(self):
        """Retry attempt limit exceeded forces BLOCKED decision and zero recovery action."""
        p_failed_3 = Payment(
            id=str(uuid.uuid4()),
            amount=50.0,
            currency="USD",
            status="failed",
            customer_id="cust_wf_6",
            merchant_id="merch_wf_1",
            description="Failed payment 3"
        )
        self.db.add(p_failed_3)
        self.db.commit()

        response = self.client.post(f"/payments/{p_failed_3.id}/execute-recovery?retry_count=3")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["outcome"], WorkflowOutcome.BLOCKED.value)
        self.assertEqual(data["policy_decision"], "BLOCKED")
        self.assertEqual(data["recovered_amount"], 0.0)
        self.assertEqual(data["new_payment_status"], "failed")

    def test_escalated_disputed_payment(self):
        """Disputed payment requires human review and returns ESCALATED outcome with zero automated recovery."""
        response = self.client.post(f"/payments/{self.p_disputed.id}/execute-recovery")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["outcome"], WorkflowOutcome.ESCALATED.value)
        self.assertEqual(data["policy_decision"], "ESCALATED")
        self.assertEqual(data["recovered_amount"], 0.0)
        self.assertEqual(data["new_payment_status"], "disputed")

    def test_workflow_payment_not_found(self):
        """Request for non-existent payment ID returns HTTP 404."""
        response = self.client.post("/payments/non_existent_wf_999/execute-recovery")
        self.assertEqual(response.status_code, 404)

if __name__ == "__main__":
    unittest.main()
