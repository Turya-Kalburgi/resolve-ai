from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models import Payment

DEMO_SCENARIO_SPECS: List[Dict[str, Any]] = [
    # SC-01: Standard Payment Failure (Successful Customer Retry) -> RECOVERED (8 payments)
    {"id": "demo_sc01_01", "amount": 150.00, "currency": "USD", "status": "failed", "customer_id": "cust_101", "merchant_id": "merch_1", "description": "SaaS Subscription Renewal", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc01_02", "amount": 220.50, "currency": "USD", "status": "failed", "customer_id": "cust_102", "merchant_id": "merch_1", "description": "E-commerce Checkout Order #401", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc01_03", "amount": 95.00, "currency": "USD", "status": "failed", "customer_id": "cust_103", "merchant_id": "merch_2", "description": "Digital Product Download", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc01_04", "amount": 310.00, "currency": "EUR", "status": "failed", "customer_id": "cust_104", "merchant_id": "merch_2", "description": "Enterprise Tier Monthly Billing", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc01_05", "amount": 180.00, "currency": "EUR", "status": "failed", "customer_id": "cust_105", "merchant_id": "merch_3", "description": "Cloud Service Plan Upgrade", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc01_06", "amount": 75.25, "currency": "GBP", "status": "failed", "customer_id": "cust_106", "merchant_id": "merch_3", "description": "API Credit Top-Up", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc01_07", "amount": 240.00, "currency": "GBP", "status": "failed", "customer_id": "cust_107", "merchant_id": "merch_4", "description": "Marketplace Order #882", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc01_08", "amount": 125.00, "currency": "CAD", "status": "failed", "customer_id": "cust_108", "merchant_id": "merch_4", "description": "Annual Premium Membership", "retry_count": 0, "simulate_success": True},

    # SC-02: Persistent Payment Failure (Customer Retry Fails) -> FAILED (4 payments)
    {"id": "demo_sc02_01", "amount": 190.00, "currency": "USD", "status": "failed", "customer_id": "cust_109", "merchant_id": "merch_1", "description": "Monthly Software Subscription", "retry_count": 0, "simulate_success": False},
    {"id": "demo_sc02_02", "amount": 85.00, "currency": "EUR", "status": "failed", "customer_id": "cust_110", "merchant_id": "merch_2", "description": "In-App Addon Purchase", "retry_count": 0, "simulate_success": False},
    {"id": "demo_sc02_03", "amount": 140.00, "currency": "GBP", "status": "failed", "customer_id": "cust_111", "merchant_id": "merch_3", "description": "Domain Name Renewal", "retry_count": 0, "simulate_success": False},
    {"id": "demo_sc02_04", "amount": 210.00, "currency": "CAD", "status": "failed", "customer_id": "cust_112", "merchant_id": "merch_4", "description": "Hardware Spare Part Order", "retry_count": 0, "simulate_success": False},

    # SC-03: Max Retry Threshold Exceeded -> BLOCKED (4 payments)
    {"id": "demo_sc03_01", "amount": 450.00, "currency": "USD", "status": "failed", "customer_id": "cust_113", "merchant_id": "merch_1", "description": "High Value Hardware Order", "retry_count": 3, "simulate_success": True},
    {"id": "demo_sc03_02", "amount": 280.00, "currency": "EUR", "status": "failed", "customer_id": "cust_114", "merchant_id": "merch_2", "description": "Consulting Service Invoice", "retry_count": 3, "simulate_success": True},
    {"id": "demo_sc03_03", "amount": 160.00, "currency": "GBP", "status": "failed", "customer_id": "cust_115", "merchant_id": "merch_3", "description": "Recurring Training Pass", "retry_count": 3, "simulate_success": True},
    {"id": "demo_sc03_04", "amount": 320.00, "currency": "CAD", "status": "failed", "customer_id": "cust_116", "merchant_id": "merch_4", "description": "Server Hosting Renewal", "retry_count": 4, "simulate_success": True},

    # SC-04: Active Chargeback / Bank Dispute -> ESCALATED (4 payments)
    {"id": "demo_sc04_01", "amount": 500.00, "currency": "USD", "status": "disputed", "customer_id": "cust_117", "merchant_id": "merch_1", "description": "Disputed E-Commerce Checkout", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc04_02", "amount": 350.00, "currency": "EUR", "status": "disputed", "customer_id": "cust_118", "merchant_id": "merch_2", "description": "Chargeback on Annual License", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc04_03", "amount": 220.00, "currency": "GBP", "status": "disputed", "customer_id": "cust_119", "merchant_id": "merch_3", "description": "Disputed Digital Download", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc04_04", "amount": 400.00, "currency": "CAD", "status": "disputed", "customer_id": "cust_120", "merchant_id": "merch_4", "description": "Bank Fraud Investigation Item", "retry_count": 0, "simulate_success": True},

    # SC-05: Pending Gateway Settlement -> MONITORING (4 payments)
    {"id": "demo_sc05_01", "amount": 130.00, "currency": "USD", "status": "pending", "customer_id": "cust_121", "merchant_id": "merch_1", "description": "Pending ACH Bank Transfer", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc05_02", "amount": 260.00, "currency": "EUR", "status": "pending", "customer_id": "cust_122", "merchant_id": "merch_2", "description": "SEPA Direct Debit Pending", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc05_03", "amount": 115.00, "currency": "GBP", "status": "pending", "customer_id": "cust_123", "merchant_id": "merch_3", "description": "BACS Settlement Processing", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc05_04", "amount": 175.00, "currency": "CAD", "status": "pending", "customer_id": "cust_124", "merchant_id": "merch_4", "description": "E-Transfer Verification Pending", "retry_count": 0, "simulate_success": True},

    # SC-06: Completed Payment -> NO_ACTION (4 payments)
    {"id": "demo_sc06_01", "amount": 300.00, "currency": "USD", "status": "completed", "customer_id": "cust_125", "merchant_id": "merch_1", "description": "Completed Monthly Renewal", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc06_02", "amount": 420.00, "currency": "EUR", "status": "completed", "customer_id": "cust_126", "merchant_id": "merch_2", "description": "Successfully Settled Order", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc06_03", "amount": 195.00, "currency": "GBP", "status": "completed", "customer_id": "cust_127", "merchant_id": "merch_3", "description": "Cleared Gateway Transaction", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc06_04", "amount": 250.00, "currency": "CAD", "status": "completed", "customer_id": "cust_128", "merchant_id": "merch_4", "description": "Verified Successful Checkout", "retry_count": 0, "simulate_success": True},

    # SC-07: Low AI Confidence Score (Unrecognized Status) -> ESCALATED (2 payments)
    {"id": "demo_sc07_01", "amount": 380.00, "currency": "USD", "status": "declined_unknown", "customer_id": "cust_129", "merchant_id": "merch_1", "description": "Ambiguous Error Response Code", "retry_count": 0, "simulate_success": True},
    {"id": "demo_sc07_02", "amount": 290.00, "currency": "EUR", "status": "declined_unknown", "customer_id": "cust_130", "merchant_id": "merch_2", "description": "Unrecognized Terminal Code", "retry_count": 0, "simulate_success": True},
]

def seed_demo_synthetic_payments(db: Session) -> int:
    """
    Populates database with exactly 30 deterministic synthetic demo payment records.
    Replaces existing records safely if requested.
    """
    created_count = 0
    for spec in DEMO_SCENARIO_SPECS:
        existing = db.query(Payment).filter(Payment.id == spec["id"]).first()
        if not existing:
            payment = Payment(
                id=spec["id"],
                amount=spec["amount"],
                currency=spec["currency"],
                status=spec["status"],
                customer_id=spec["customer_id"],
                merchant_id=spec["merchant_id"],
                description=spec["description"]
            )
            db.add(payment)
            created_count += 1
    db.commit()
    return created_count
