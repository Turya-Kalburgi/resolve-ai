from datetime import datetime, timezone
from typing import List
from app.models import Payment
from app.schemas_recovery import RecoveryRecommendationResponse, RecoveryActionType, RecoveryStrategy
from app.schemas_policy import (
    PolicyEvaluationResponse,
    PolicyDecision,
    PolicyRuleResult
)

ALLOWED_ACTION_TYPES = {
    RecoveryActionType.PROMPT_RETRY,
    RecoveryActionType.HUMAN_REVIEW,
    RecoveryActionType.STATUS_MONITOR,
    RecoveryActionType.NO_OP
}

CONFIDENCE_THRESHOLD = 0.70
MAX_ALLOWED_RETRIES = 3

def evaluate_policy(
    payment: Payment,
    recommendation: RecoveryRecommendationResponse,
    retry_count: int = 0
) -> PolicyEvaluationResponse:
    """
    Deterministic Policy & Safety Engine evaluating AI recovery recommendations
    against strict business and safety rules. Returns APPROVED, BLOCKED, or ESCALATED.
    """
    now = datetime.now(timezone.utc)
    rules_evaluated: List[PolicyRuleResult] = []
    violations: List[str] = []

    # Rule 1: Payment Already Completed
    status_lower = (payment.status or "").lower()
    if status_lower == "completed" and recommendation.action_type != RecoveryActionType.NO_OP:
        r1 = PolicyRuleResult(
            rule_id="RULE_001",
            rule_name="PAYMENT_ALREADY_COMPLETED",
            passed=False,
            severity="BLOCK",
            message="Payment status is 'completed'. Further recovery actions are blocked to prevent duplicate billing."
        )
        violations.append(r1.message)
    else:
        r1 = PolicyRuleResult(
            rule_id="RULE_001",
            rule_name="PAYMENT_ALREADY_COMPLETED",
            passed=True,
            severity="INFO",
            message="Payment is not completed or action is NO_OP."
        )
    rules_evaluated.append(r1)

    # Rule 2: Max Retries Exceeded
    if recommendation.action_type == RecoveryActionType.PROMPT_RETRY and retry_count >= MAX_ALLOWED_RETRIES:
        r2 = PolicyRuleResult(
            rule_id="RULE_002",
            rule_name="MAX_RETRIES_EXCEEDED",
            passed=False,
            severity="BLOCK",
            message=f"Retry attempt limit reached ({retry_count} >= {MAX_ALLOWED_RETRIES}). Automated retries are blocked."
        )
        violations.append(r2.message)
    else:
        r2 = PolicyRuleResult(
            rule_id="RULE_002",
            rule_name="MAX_RETRIES_EXCEEDED",
            passed=True,
            severity="INFO",
            message=f"Retry count ({retry_count}) is within permissible limit (< {MAX_ALLOWED_RETRIES})."
        )
    rules_evaluated.append(r2)

    # Rule 3: Low Confidence Score
    if recommendation.confidence_score < CONFIDENCE_THRESHOLD:
        r3 = PolicyRuleResult(
            rule_id="RULE_003",
            rule_name="LOW_CONFIDENCE_SCORE",
            passed=False,
            severity="ESCALATE",
            message=f"AI recommendation confidence score ({recommendation.confidence_score:.2f}) is below threshold ({CONFIDENCE_THRESHOLD}). Mandatory human review required."
        )
        violations.append(r3.message)
    else:
        r3 = PolicyRuleResult(
            rule_id="RULE_003",
            rule_name="LOW_CONFIDENCE_SCORE",
            passed=True,
            severity="INFO",
            message=f"Confidence score ({recommendation.confidence_score:.2f}) meets or exceeds threshold."
        )
    rules_evaluated.append(r3)

    # Rule 4: Active Dispute / Escalation
    if status_lower == "disputed" or recommendation.recommended_strategy == RecoveryStrategy.HUMAN_DISPUTE_INVESTIGATION or recommendation.requires_human_escalation:
        r4 = PolicyRuleResult(
            rule_id="RULE_004",
            rule_name="ACTIVE_DISPUTE_ESCALATION",
            passed=False,
            severity="ESCALATE",
            message="Active chargeback/dispute or explicit escalation flag requires human dispute team review."
        )
        violations.append(r4.message)
    else:
        r4 = PolicyRuleResult(
            rule_id="RULE_004",
            rule_name="ACTIVE_DISPUTE_ESCALATION",
            passed=True,
            severity="INFO",
            message="No active dispute or escalation flag detected."
        )
    rules_evaluated.append(r4)

    # Rule 5: Missing Required Info
    if not payment.id or not recommendation.explanation:
        r5 = PolicyRuleResult(
            rule_id="RULE_005",
            rule_name="MISSING_REQUIRED_INFO",
            passed=False,
            severity="ESCALATE",
            message="Required payment ID or recommendation explanation is missing."
        )
        violations.append(r5.message)
    else:
        r5 = PolicyRuleResult(
            rule_id="RULE_005",
            rule_name="MISSING_REQUIRED_INFO",
            passed=True,
            severity="INFO",
            message="All required payment and recommendation fields are present."
        )
    rules_evaluated.append(r5)

    # Rule 6: Disallowed Action Type
    if recommendation.action_type not in ALLOWED_ACTION_TYPES:
        r6 = PolicyRuleResult(
            rule_id="RULE_006",
            rule_name="DISALLOWED_ACTION_TYPE",
            passed=False,
            severity="BLOCK",
            message=f"Action type '{recommendation.action_type}' is not authorized by safety policy."
        )
        violations.append(r6.message)
    else:
        r6 = PolicyRuleResult(
            rule_id="RULE_006",
            rule_name="DISALLOWED_ACTION_TYPE",
            passed=True,
            severity="INFO",
            message=f"Action type '{recommendation.action_type.value}' is recognized and allowed."
        )
    rules_evaluated.append(r6)

    # Decision Resolution Logic
    has_block = any(r.severity == "BLOCK" and not r.passed for r in rules_evaluated)
    has_escalate = any(r.severity == "ESCALATE" and not r.passed for r in rules_evaluated)

    if has_block:
        decision = PolicyDecision.BLOCKED
        primary_reason = "Recommended action blocked by safety policy: " + "; ".join(
            r.message for r in rules_evaluated if r.severity == "BLOCK" and not r.passed
        )
    elif has_escalate:
        decision = PolicyDecision.ESCALATED
        primary_reason = "Recommended action requires human escalation: " + "; ".join(
            r.message for r in rules_evaluated if r.severity == "ESCALATE" and not r.passed
        )
    else:
        decision = PolicyDecision.APPROVED
        primary_reason = "All safety policy rules passed successfully. Recommendation authorized for execution."

    return PolicyEvaluationResponse(
        payment_id=payment.id,
        decision=decision,
        recommended_action=recommendation.action_type.value if hasattr(recommendation.action_type, "value") else str(recommendation.action_type),
        primary_reason=primary_reason,
        rules_evaluated=rules_evaluated,
        violations=violations,
        evaluated_at=now
    )
