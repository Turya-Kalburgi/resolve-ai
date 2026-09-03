from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import Payment
from app.schemas import PaymentResponse, PaymentListResponse

router = APIRouter(prefix="/payments", tags=["Payments"])

@router.get("", response_model=PaymentListResponse)
def get_payments(
    status: Optional[str] = Query(None, description="Filter payments by status (completed, pending, failed, disputed)"),
    customer_id: Optional[str] = Query(None, description="Filter payments by customer_id"),
    limit: int = Query(20, ge=1, le=100, description="Max number of payments to return"),
    offset: int = Query(0, ge=0, description="Number of payments to skip"),
    db: Session = Depends(get_db)
):
    """
    Retrieve a list of payments with optional filtering by status and customer_id.
    """
    query = db.query(Payment)
    if status:
        query = query.filter(Payment.status == status)
    if customer_id:
        query = query.filter(Payment.customer_id == customer_id)
    
    total = query.count()
    payments = query.order_by(Payment.created_at.desc()).offset(offset).limit(limit).all()
    
    return PaymentListResponse(total=total, payments=payments)

@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment_by_id(payment_id: str, db: Session = Depends(get_db)):
    """
    Retrieve details for a specific payment by payment_id.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID '{payment_id}' not found"
        )
    return payment
