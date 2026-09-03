import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.seed import seed_synthetic_payments

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_resolve_ai.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

class TestPaymentsAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        db = TestingSessionLocal()
        seed_synthetic_payments(db, count=15)
        db.close()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)

    def test_read_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ResolveAI", response.text)

    def test_get_payments_list(self):
        response = self.client.get("/payments")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total", data)
        self.assertIn("payments", data)
        self.assertGreaterEqual(data["total"], 15)
        self.assertTrue(len(data["payments"]) > 0)

    def test_get_payments_with_filter(self):
        # Fetch first payment to get a customer_id
        res_all = self.client.get("/payments")
        sample_payment = res_all.json()["payments"][0]
        customer_id = sample_payment["customer_id"]

        response = self.client.get(f"/payments?customer_id={customer_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for item in data["payments"]:
            self.assertEqual(item["customer_id"], customer_id)

    def test_get_payment_by_id_success(self):
        res_all = self.client.get("/payments")
        sample_payment = res_all.json()["payments"][0]
        payment_id = sample_payment["id"]

        response = self.client.get(f"/payments/{payment_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], payment_id)

    def test_get_payment_by_id_not_found(self):
        response = self.client.get("/payments/non_existent_id_99999")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("not found", data["detail"].lower())

if __name__ == "__main__":
    unittest.main()
