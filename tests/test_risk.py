import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

from app.database import Base, get_db
from app.main import app
from app.models import Payment
from app.schemas_risk import RiskLevel, RiskCategory

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_resolve_ai.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

class TestRiskAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        cls.db = TestingSessionLocal()

        # Create explicit test payments for each status rule
        cls.p_disputed = Payment(
            id=str(uuid.uuid4()),
            amount=150.0,
            currency="USD",
            status="disputed",
            customer_id="cust_risk_1",
            merchant_id="merch_risk_1",
            description="Test disputed payment"
        )
        cls.p_failed = Payment(
            id=str(uuid.uuid4()),
            amount=75.0,
            currency="USD",
            status="failed",
            customer_id="cust_risk_2",
            merchant_id="merch_risk_1",
            description="Test failed payment"
        )
        cls.p_pending = Payment(
            id=str(uuid.uuid4()),
            amount=50.0,
            currency="USD",
            status="pending",
            customer_id="cust_risk_3",
            merchant_id="merch_risk_1",
            description="Test pending payment"
        )
        cls.p_completed = Payment(
            id=str(uuid.uuid4()),
            amount=200.0,
            currency="USD",
            status="completed",
            customer_id="cust_risk_4",
            merchant_id="merch_risk_1",
            description="Test completed payment"
        )

        cls.db.add_all([cls.p_disputed, cls.p_failed, cls.p_pending, cls.p_completed])
        cls.db.commit()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_risk_disputed_payment(self):
        response = self.client.get(f"/payments/{self.p_disputed.id}/risk")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["payment_id"], self.p_disputed.id)
        self.assertEqual(data["risk_level"], RiskLevel.CRITICAL.value)
        self.assertEqual(data["risk_score"], 0.90)
        self.assertEqual(data["category"], RiskCategory.DISPUTE_CHARGEBACK.value)
        self.assertTrue(data["is_flagged"])
        self.assertEqual(data["diagnosis"]["recommended_action"], "ESCALATE_TO_HUMAN_DISPUTE_TEAM")

    def test_risk_failed_payment(self):
        response = self.client.get(f"/payments/{self.p_failed.id}/risk")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["payment_id"], self.p_failed.id)
        self.assertEqual(data["risk_level"], RiskLevel.HIGH.value)
        self.assertEqual(data["risk_score"], 0.70)
        self.assertEqual(data["category"], RiskCategory.PAYMENT_FAILURE.value)
        self.assertTrue(data["is_flagged"])
        self.assertEqual(data["diagnosis"]["recommended_action"], "PROMPT_CUSTOMER_RETRY_OR_CHECK_GATEWAY")

    def test_risk_pending_payment(self):
        response = self.client.get(f"/payments/{self.p_pending.id}/risk")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["payment_id"], self.p_pending.id)
        self.assertEqual(data["risk_level"], RiskLevel.MEDIUM.value)
        self.assertEqual(data["risk_score"], 0.40)
        self.assertEqual(data["category"], RiskCategory.PENDING_SETTLEMENT.value)
        self.assertFalse(data["is_flagged"])
        self.assertEqual(data["diagnosis"]["recommended_action"], "MONITOR_SETTLEMENT_STATUS")

    def test_risk_completed_payment(self):
        response = self.client.get(f"/payments/{self.p_completed.id}/risk")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["payment_id"], self.p_completed.id)
        self.assertEqual(data["risk_level"], RiskLevel.LOW.value)
        self.assertEqual(data["risk_score"], 0.05)
        self.assertEqual(data["category"], RiskCategory.LOW_RISK_NORMAL.value)
        self.assertFalse(data["is_flagged"])
        self.assertEqual(data["diagnosis"]["recommended_action"], "NO_ACTION_REQUIRED")

    def test_risk_payment_not_found(self):
        response = self.client.get("/payments/non_existent_id_99999/risk")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("not found", data["detail"].lower())

if __name__ == "__main__":
    unittest.main()
