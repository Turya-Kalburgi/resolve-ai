from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import Payment
from app.schemas_recovery import RecoveryRecommendationResponse, RecoveryActionType
from app.schemas_policy import PolicyEvaluationResponse, PolicyDecision
from app.schemas_workflow import (
    RecoveryWorkflowResponse,
    WorkflowOutcome,
    WorkflowStepLog
)

def execute_recovery_workflow(
    payment: Payment,
    recommendation: RecoveryRecommendationResponse,
    policy_evaluation: PolicyEvaluationResponse,
    simulate_success: bool = True,
    db: Optional[Session] = None
) -> RecoveryWorkflowResponse:
    """
    Simulates bounded recovery workflows (Phase 5) strictly gated by Phase 4 Policy Engine decisions.
    Performs zero real financial transactions or money movement.
    """
    now = datetime.now(timezone.utc)
    logs: List[WorkflowStepLog] = []

    # Step 1: Policy Gate Check
    if policy_evaluation.decision == PolicyDecision.BLOCKED:
        logs.append(WorkflowStepLog(
            step_number=1,
            step_name="POLICY_GATE",
            status="BLOCKED",
            details=f"Execution blocked by safety policy: {policy_evaluation.primary_reason}",
            timestamp=now
        ))
        return RecoveryWorkflowResponse(
            payment_id=payment.id,
            outcome=WorkflowOutcome.BLOCKED,
            policy_decision=policy_evaluation.decision.value if hasattr(policy_evaluation.decision, "value") else str(policy_evaluation.decision),
            action_attempted=recommendation.action_type.value if hasattr(recommendation.action_type, "value") else str(recommendation.action_type),
            recovered_amount=0.0,
            currency=payment.currency,
            previous_payment_status=payment.status,
            new_payment_status=payment.status,
            execution_logs=logs,
            executed_at=now
        )

    if policy_evaluation.decision == PolicyDecision.ESCALATED:
        logs.append(WorkflowStepLog(
            step_number=1,
            step_name="POLICY_GATE",
            status="ESCALATED",
            details=f"Execution routed to human review: {policy_evaluation.primary_reason}",
            timestamp=now
        ))
        return RecoveryWorkflowResponse(
            payment_id=payment.id,
            outcome=WorkflowOutcome.ESCALATED,
            policy_decision=policy_evaluation.decision.value if hasattr(policy_evaluation.decision, "value") else str(policy_evaluation.decision),
            action_attempted=recommendation.action_type.value if hasattr(recommendation.action_type, "value") else str(recommendation.action_type),
            recovered_amount=0.0,
            currency=payment.currency,
            previous_payment_status=payment.status,
            new_payment_status=payment.status,
            execution_logs=logs,
            executed_at=now
        )

    # Step 2: Policy Approved -> Execute Simulated Action
    logs.append(WorkflowStepLog(
        step_number=1,
        step_name="POLICY_GATE",
        status="SUCCESS",
        details="Safety policy approved recommendation for execution.",
        timestamp=now
    ))

    action = recommendation.action_type
    prev_status = payment.status

    if action == RecoveryActionType.PROMPT_RETRY:
        if simulate_success:
            outcome = WorkflowOutcome.RECOVERED
            recovered_amount = payment.amount
            new_status = "completed"
            details = f"Simulated customer retry succeeded. Recovered {recovered_amount} {payment.currency}."
            if db:
                payment.status = "completed"
                db.commit()
        else:
            outcome = WorkflowOutcome.FAILED
            recovered_amount = 0.0
            new_status = prev_status
            details = "Simulated customer retry failed. Payment remains in failed status."

    elif action == RecoveryActionType.STATUS_MONITOR:
        outcome = WorkflowOutcome.MONITORING
        recovered_amount = 0.0
        new_status = prev_status
        details = "Settlement monitoring initiated. Awaiting bank/gateway settlement; zero revenue recovered at this step."

    elif action == RecoveryActionType.NO_OP:
        outcome = WorkflowOutcome.NO_ACTION
        recovered_amount = 0.0
        new_status = prev_status
        details = "Payment is already completed. No recovery action required; zero additional revenue recovered."

    else:
        outcome = WorkflowOutcome.ESCALATED
        recovered_amount = 0.0
        new_status = prev_status
        details = "Action requires manual review. No automated simulation executed."

    logs.append(WorkflowStepLog(
        step_number=2,
        step_name="SIMULATED_ACTION_EXECUTION",
        status=outcome.value,
        details=details,
        timestamp=now
    ))

    return RecoveryWorkflowResponse(
        payment_id=payment.id,
        outcome=outcome,
        policy_decision=policy_evaluation.decision.value if hasattr(policy_evaluation.decision, "value") else str(policy_evaluation.decision),
        action_attempted=action.value if hasattr(action, "value") else str(action),
        recovered_amount=recovered_amount,
        currency=payment.currency,
        previous_payment_status=prev_status,
        new_payment_status=new_status,
        execution_logs=logs,
        executed_at=now
    )
