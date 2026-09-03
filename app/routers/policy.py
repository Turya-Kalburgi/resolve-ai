from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Payment
from app.schemas_policy import PolicyEvaluationResponse
from app.services.risk_engine import evaluate_payment_risk
from app.services.recovery_agent import generate_recovery_recommendation
from app.services.policy_engine import evaluate_policy

router = APIRouter(prefix="/payments", tags=["Policy & Safety Engine"])

@router.get("/{payment_id}/policy", response_model=PolicyEvaluationResponse)
def evaluate_payment_policy(
    payment_id: str,
    retry_count: int = Query(0, ge=0, description="Number of previous retry attempts for this payment"),
    db: Session = Depends(get_db)
):
    """
    Evaluates payment risk (Phase 2), generates AI recovery recommendation (Phase 3),
    and applies deterministic safety policies (Phase 4) to produce a final APPROVED,
    BLOCKED, or ESCALATED policy decision.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID '{payment_id}' not found"
        )
    
    risk_assessment = evaluate_payment_risk(payment)
    recommendation = generate_recovery_recommendation(risk_assessment)
    policy_evaluation = evaluate_policy(payment, recommendation, retry_count=retry_count)
    return policy_evaluation
