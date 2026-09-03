import time
from datetime import datetime, timezone
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models_checkout import CheckoutSession
from app.models_audit import AuditLog
from app.seed_checkout import CHECKOUT_SCENARIO_SPECS, seed_synthetic_checkouts
from app.services.risk_engine import evaluate_checkout_risk
from app.services.recovery_agent import generate_recovery_recommendation
from app.services.policy_engine import evaluate_policy
from app.schemas_workflow import RecoveryWorkflowResponse, WorkflowOutcome, WorkflowStepLog
from app.schemas_policy import PolicyDecision
from app.services.metrics_service import record_audit_log

def run_checkout_batch_evaluation(db: Session, reset_db: bool = False) -> Dict[str, Any]:
    """
    Executes the 6-checkout synthetic evaluation batch through Checkout Risk -> Recovery Agent -> Policy Engine -> Simulated Workflow -> Audit Log -> Separate Checkout Metrics.
    Completely isolated from the 30-payment payment recovery benchmark.
    """
    start_time = time.time()
    now = datetime.now(timezone.utc)

    if reset_db:
        # Clear existing checkout sessions
        db.query(CheckoutSession).delete()
        db.commit()

    seed_synthetic_checkouts(db)

    outcomes_breakdown: Dict[str, int] = {
        "RECOVERED": 0,
        "FAILED": 0,
        "BLOCKED": 0,
        "ESCALATED": 0,
        "MONITORING": 0,
        "NO_ACTION": 0
    }

    by_currency: Dict[str, Dict[str, Any]] = {}
    processed_count = 0

    for spec in CHECKOUT_SCENARIO_SPECS:
        checkout = db.query(CheckoutSession).filter(CheckoutSession.id == spec["id"]).first()
        if not checkout:
            continue

        retry_count = spec.get("retry_count", 0)
        simulate_success = spec.get("simulate_success", True)
        setattr(checkout, "retry_count", retry_count)

        initial_status = checkout.status
        curr = checkout.currency

        if curr not in by_currency:
            by_currency[curr] = {
                "total_checkout_sessions": 0,
                "revenue_at_risk": 0.0,
                "revenue_recovered": 0.0,
                "recovered_count": 0,
                "failed_count": 0,
                "blocked_count": 0,
                "escalated_count": 0,
                "recovery_rate_percentage": 0.0
            }

        curr_stats = by_currency[curr]
        curr_stats["total_checkout_sessions"] += 1

        if initial_status == "ABANDONED":
            curr_stats["revenue_at_risk"] += checkout.amount

        # 1. Checkout Risk Engine
        risk_assessment = evaluate_checkout_risk(checkout)

        # 2. Recovery Recommendation
        recommendation = generate_recovery_recommendation(risk_assessment)

        # 3. Policy Engine Evaluation (Governed by RULE_001..RULE_006)
        policy_evaluation = evaluate_policy(checkout, recommendation, retry_count=retry_count)

        # 4. Workflow Execution Simulation
        action_attempted = recommendation.action_type.value if hasattr(recommendation.action_type, "value") else str(recommendation.action_type)
        new_status = initial_status
        recovered_amt = 0.0

        if policy_evaluation.decision == PolicyDecision.BLOCKED:
            outcome = WorkflowOutcome.BLOCKED
            curr_stats["blocked_count"] += 1
        elif policy_evaluation.decision == PolicyDecision.ESCALATED:
            outcome = WorkflowOutcome.ESCALATED
            curr_stats["escalated_count"] += 1
        elif recommendation.action_type.value == "NO_OP":
            outcome = WorkflowOutcome.NO_ACTION
        elif recommendation.action_type.value == "STATUS_MONITOR":
            outcome = WorkflowOutcome.MONITORING
        else:
            # PROMPT_RETRY (Checkout Recovery Nudge)
            if simulate_success:
                outcome = WorkflowOutcome.RECOVERED
                recovered_amt = checkout.amount
                new_status = "COMPLETED"
                curr_stats["recovered_count"] += 1
                curr_stats["revenue_recovered"] += recovered_amt
            else:
                outcome = WorkflowOutcome.FAILED
                new_status = "ABANDONED"
                curr_stats["failed_count"] += 1

        workflow_response = RecoveryWorkflowResponse(
            payment_id=checkout.id,
            outcome=outcome,
            policy_decision=policy_evaluation.decision.value if hasattr(policy_evaluation.decision, "value") else str(policy_evaluation.decision),
            action_attempted=action_attempted,
            recovered_amount=recovered_amt,
            currency=checkout.currency,
            previous_payment_status=initial_status,
            new_payment_status=new_status,
            execution_logs=[
                WorkflowStepLog(
                    step_number=1,
                    step_name="CHECKOUT_RECOVERY_NUDGE",
                    status="SIMULATED_SUCCESS" if outcome == WorkflowOutcome.RECOVERED else str(outcome.value),
                    details=f"Checkout nudge execution resulted in outcome '{outcome.value}'",
                    timestamp=now
                )
            ],
            executed_at=now
        )

        # 5. Record Immutable Audit Trail
        record_audit_log(
            db=db,
            payment=checkout,
            initial_status=initial_status,
            risk_assessment=risk_assessment,
            recommendation=recommendation,
            policy_evaluation=policy_evaluation,
            workflow_response=workflow_response
        )

        outcome_key = outcome.value
        outcomes_breakdown[outcome_key] = outcomes_breakdown.get(outcome_key, 0) + 1
        processed_count += 1

    for curr, stats in by_currency.items():
        if stats["revenue_at_risk"] > 0:
            stats["recovery_rate_percentage"] = round(
                (stats["revenue_recovered"] / stats["revenue_at_risk"]) * 100.0, 2
            )
        stats["revenue_at_risk"] = round(stats["revenue_at_risk"], 2)
        stats["revenue_recovered"] = round(stats["revenue_recovered"], 2)

    elapsed_sec = round(time.time() - start_time, 4)

    return {
        "total_checkout_sessions_evaluated": processed_count,
        "outcomes_breakdown": outcomes_breakdown,
        "by_currency": by_currency,
        "execution_time_seconds": elapsed_sec,
        "evaluated_at": now
    }
