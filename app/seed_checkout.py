from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models_checkout import CheckoutSession

CHECKOUT_SCENARIO_SPECS: List[Dict[str, Any]] = [
    # 1. USD Abandoned Checkout -> RECOVERED ($120.00 USD)
    {"id": "chk_sc01_01", "customer_id": "cust_chk_201", "merchant_id": "merch_1", "amount": 120.00, "currency": "USD", "status": "ABANDONED", "payment_attempted": False, "description": "Abandoned Cart #1001", "retry_count": 0, "simulate_success": True},

    # 2. EUR Abandoned Checkout -> RECOVERED (€180.00 EUR)
    {"id": "chk_sc01_02", "customer_id": "cust_chk_202", "merchant_id": "merch_2", "amount": 180.00, "currency": "EUR", "status": "ABANDONED", "payment_attempted": False, "description": "Abandoned Checkout - Software License", "retry_count": 0, "simulate_success": True},

    # 3. GBP Abandoned Checkout -> RECOVERED (£95.00 GBP)
    {"id": "chk_sc01_03", "customer_id": "cust_chk_203", "merchant_id": "merch_3", "amount": 95.00, "currency": "GBP", "status": "ABANDONED", "payment_attempted": True, "description": "Abandoned Checkout - Digital Course", "retry_count": 0, "simulate_success": True},

    # 4. CAD Abandoned Checkout -> FAILED ($210.00 CAD, customer ignores reminder)
    {"id": "chk_sc02_01", "customer_id": "cust_chk_204", "merchant_id": "merch_4", "amount": 210.00, "currency": "CAD", "status": "ABANDONED", "payment_attempted": False, "description": "Abandoned Cart #2004", "retry_count": 0, "simulate_success": False},

    # 5. USD Abandoned Checkout -> BLOCKED ($350.00 USD, retry_count >= 3 limit exceeded)
    {"id": "chk_sc03_01", "customer_id": "cust_chk_205", "merchant_id": "merch_1", "amount": 350.00, "currency": "USD", "status": "ABANDONED", "payment_attempted": False, "description": "Abandoned High Value Checkout", "retry_count": 3, "simulate_success": True},

    # 6. EUR Active Checkout -> MONITORING / ESCALATED (€250.00 EUR, STARTED status)
    {"id": "chk_sc04_01", "customer_id": "cust_chk_206", "merchant_id": "merch_2", "amount": 250.00, "currency": "EUR", "status": "STARTED", "payment_attempted": False, "description": "Active In-Progress Checkout", "retry_count": 0, "simulate_success": True},
]

def seed_synthetic_checkouts(db: Session) -> int:
    """
    Populates database with exactly 6 deterministic synthetic checkout session records.
    """
    created_count = 0
    for spec in CHECKOUT_SCENARIO_SPECS:
        existing = db.query(CheckoutSession).filter(CheckoutSession.id == spec["id"]).first()
        if not existing:
            checkout = CheckoutSession(
                id=spec["id"],
                customer_id=spec["customer_id"],
                merchant_id=spec["merchant_id"],
                amount=spec["amount"],
                currency=spec["currency"],
                status=spec["status"],
                payment_attempted=spec["payment_attempted"],
                description=spec["description"]
            )
            db.add(checkout)
            created_count += 1
    db.commit()
    return created_count
