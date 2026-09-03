from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Payment
from app.schemas_risk import RiskAssessmentResponse
from app.services.risk_engine import evaluate_payment_risk

router = APIRouter(prefix="/payments", tags=["Risk & Diagnosis"])

@router.get("/{payment_id}/risk", response_model=RiskAssessmentResponse)
def get_payment_risk_assessment(payment_id: str, db: Session = Depends(get_db)):
    """
    Evaluates and returns the deterministic risk assessment and diagnosis for a specific payment by payment_id.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID '{payment_id}' not found"
        )
    return evaluate_payment_risk(payment)
