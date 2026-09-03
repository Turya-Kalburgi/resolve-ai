from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Payment
from app.schemas_workflow import RecoveryWorkflowResponse
from app.services.risk_engine import evaluate_payment_risk
from app.services.recovery_agent import generate_recovery_recommendation
from app.services.policy_engine import evaluate_policy
from app.services.workflow_engine import execute_recovery_workflow
from app.services.metrics_service import record_audit_log

router = APIRouter(prefix="/payments", tags=["Simulated Recovery Workflow Engine"])

@router.post("/{payment_id}/execute-recovery", response_model=RecoveryWorkflowResponse)
def execute_payment_recovery_workflow(
    payment_id: str,
    retry_count: int = Query(0, ge=0, description="Number of previous retry attempts for this payment"),
    simulate_success: bool = Query(True, description="Controls simulated gateway/retry outcome for testing"),
    db: Session = Depends(get_db)
):
    """
    Executes a bounded simulated recovery workflow for a payment.
    Pipeline: Risk Diagnosis (Phase 2) -> AI Recommendation (Phase 3) -> Policy Safety Check (Phase 4) -> Workflow Engine (Phase 5).
    Performs zero real money movement or external gateway requests.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID '{payment_id}' not found"
        )

    initial_status = payment.status
    risk_assessment = evaluate_payment_risk(payment)
    recommendation = generate_recovery_recommendation(risk_assessment)
    policy_evaluation = evaluate_policy(payment, recommendation, retry_count=retry_count)
    workflow_response = execute_recovery_workflow(
        payment=payment,
        recommendation=recommendation,
        policy_evaluation=policy_evaluation,
        simulate_success=simulate_success,
        db=db
    )
    
    # Audit trail persistence (Phase 6)
    record_audit_log(
        db=db,
        payment=payment,
        initial_status=initial_status,
        risk_assessment=risk_assessment,
        recommendation=recommendation,
        policy_evaluation=policy_evaluation,
        workflow_response=workflow_response
    )
    
    return workflow_response

@router.post("/evaluate-batch")
def evaluate_synthetic_demo_batch(
    reset_db: bool = Query(True, description="Clears existing demo payments and audit logs before batch execution"),
    db: Session = Depends(get_db)
):
    """
    Executes the 30-payment synthetic evaluation dataset through the complete 6-phase pipeline.
    Produces a heterogeneous mix of outcomes (RECOVERED, FAILED, BLOCKED, ESCALATED, MONITORING, NO_ACTION)
    with zero real money movement.
    """
    from app.services.batch_evaluator import run_batch_evaluation
    return run_batch_evaluation(db, reset_db=reset_db)
