import random
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models import Payment

STATUSES = ["completed", "pending", "failed", "disputed"]
CURRENCIES = ["USD", "EUR", "GBP", "CAD"]
DESCRIPTIONS = [
    "Subscription monthly renewal",
    "E-commerce order checkout",
    "Digital download purchase",
    "SaaS tier upgrade",
    "In-app credit purchase",
    "Marketplace transaction",
    "API usage billing"
]

def seed_synthetic_payments(db: Session, count: int = 25) -> int:
    """Populates database with synthetic payment records if empty or below threshold."""
    existing_count = db.query(Payment).count()
    if existing_count >= count:
        return 0

    to_create = count - existing_count
    payments_to_add = []
    
    now = datetime.now(timezone.utc)
    for i in range(to_create):
        created = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        payment = Payment(
            id=str(uuid.uuid4()),
            amount=round(random.uniform(10.0, 500.0), 2),
            currency=random.choice(CURRENCIES),
            status=random.choice(STATUSES),
            customer_id=f"cust_{random.randint(100, 150)}",
            merchant_id=f"merch_{random.randint(1, 5)}",
            description=random.choice(DESCRIPTIONS),
            created_at=created
        )
        payments_to_add.append(payment)
    
    db.add_all(payments_to_add)
    db.commit()
    return to_create
