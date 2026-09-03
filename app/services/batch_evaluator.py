import time
from datetime import datetime, timezone
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models import Payment
from app.models_audit import AuditLog
from app.seed_demo import DEMO_SCENARIO_SPECS, seed_demo_synthetic_payments
from app.services.risk_engine import evaluate_payment_risk
from app.services.recovery_agent import generate_recovery_recommendation
from app.services.policy_engine import evaluate_policy
from app.services.workflow_engine import execute_recovery_workflow
from app.services.metrics_service import record_audit_log, compute_metrics_summary

def run_batch_evaluation(db: Session, reset_db: bool = False) -> Dict[str, Any]:
    """
    Executes the 30-payment synthetic evaluation batch through Phases 1-6 end-to-end.
    If reset_db is True, safely clears payments and audit_logs tables before running.
    Performs zero real financial API requests or money movement.
    """
    start_time = time.time()
    now = datetime.now(timezone.utc)

    if reset_db:
        db.query(AuditLog).delete()
        db.query(Payment).delete()
        db.commit()
        seed_demo_synthetic_payments(db)
    else:
        # Ensure demo payments exist
        seed_demo_synthetic_payments(db)

    outcomes_breakdown: Dict[str, int] = {
        "RECOVERED": 0,
        "FAILED": 0,
        "BLOCKED": 0,
        "ESCALATED": 0,
        "MONITORING": 0,
        "NO_ACTION": 0
    }

    # Process all 30 demo scenario specs in exact order
    processed_count = 0
    for spec in DEMO_SCENARIO_SPECS:
        payment = db.query(Payment).filter(Payment.id == spec["id"]).first()
        if not payment:
            continue

        initial_status = payment.status
        retry_count = spec.get("retry_count", 0)
        simulate_success = spec.get("simulate_success", True)

        # Pipeline Execution (Phases 2 -> 5)
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

        # Audit Persistence (Phase 6)
        record_audit_log(
            db=db,
            payment=payment,
            initial_status=initial_status,
            risk_assessment=risk_assessment,
            recommendation=recommendation,
            policy_evaluation=policy_evaluation,
            workflow_response=workflow_response
        )

        outcome_key = workflow_response.outcome.value if hasattr(workflow_response.outcome, "value") else str(workflow_response.outcome)
        outcomes_breakdown[outcome_key] = outcomes_breakdown.get(outcome_key, 0) + 1
        processed_count += 1

    metrics_summary = compute_metrics_summary(db)
    elapsed_sec = round(time.time() - start_time, 4)

    return {
        "total_payments_processed": processed_count,
        "outcomes_breakdown": outcomes_breakdown,
        "metrics_summary": metrics_summary,
        "execution_time_seconds": elapsed_sec,
        "evaluated_at": now
    }
