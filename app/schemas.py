from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class PaymentResponse(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    customer_id: str
    merchant_id: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PaymentListResponse(BaseModel):
    total: int
    payments: List[PaymentResponse]
