from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Payment
from app.schemas_recovery import RecoveryRecommendationResponse
from app.services.risk_engine import evaluate_payment_risk
from app.services.recovery_agent import generate_recovery_recommendation

router = APIRouter(prefix="/payments", tags=["AI Recovery Agent"])

@router.get("/{payment_id}/recovery", response_model=RecoveryRecommendationResponse)
def get_payment_recovery_recommendation(payment_id: str, db: Session = Depends(get_db)):
    """
    Evaluates payment risk via Phase 2 Risk Engine, then generates a structured
    AI Recovery Recommendation for the given payment_id.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID '{payment_id}' not found"
        )
    
    risk_assessment = evaluate_payment_risk(payment)
    return generate_recovery_recommendation(risk_assessment)
