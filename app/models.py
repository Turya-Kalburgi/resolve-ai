import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime
from app.database import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="USD")
    status = Column(String, nullable=False, index=True)
    customer_id = Column(String, nullable=False, index=True)
    merchant_id = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
