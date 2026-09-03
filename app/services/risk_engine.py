from typing import Any
from datetime import datetime, timezone
from app.models import Payment
from app.schemas_risk import (
    RiskAssessmentResponse,
    RiskDiagnosis,
    RiskLevel,
    RiskCategory
)

def evaluate_payment_risk(payment: Payment) -> RiskAssessmentResponse:
    """
    Deterministic rule-based engine evaluating risk and generating diagnosis
    for a Payment instance using available model fields.
    """
    now = datetime.now(timezone.utc)
    status_lower = (payment.status or "").lower()
    retry_count = getattr(payment, "retry_count", 0)

    if status_lower == "disputed":
        risk_level = RiskLevel.CRITICAL
        risk_score = 0.90
        category = RiskCategory.DISPUTE_CHARGEBACK
        is_flagged = True
        reasons = [
            "Payment status is marked as 'disputed', indicating an active customer chargeback or dispute."
        ]
        summary = "High financial risk due to an active customer dispute or chargeback."
        recommended_action = "ESCALATE_TO_HUMAN_DISPUTE_TEAM"

    elif status_lower == "failed":
        risk_level = RiskLevel.HIGH
        risk_score = 0.70
        category = RiskCategory.PAYMENT_FAILURE
        is_flagged = True
        if retry_count >= 3:
            reasons = [
                f"Payment status is 'failed' and maximum retry limit has been reached ({retry_count} prior attempts)."
            ]
            summary = f"Payment processing failed with retry limit reached ({retry_count} attempts)."
            recommended_action = "BLOCK_AUTOMATED_RETRY_OR_ESCALATE"
        else:
            reasons = [
                "Payment status is marked as 'failed', indicating transaction processing failure."
            ]
            summary = "Payment processing failed. Requires customer retry or payment gateway verification."
            recommended_action = "PROMPT_CUSTOMER_RETRY_OR_CHECK_GATEWAY"

    elif status_lower == "pending":
        risk_level = RiskLevel.MEDIUM
        risk_score = 0.40
        category = RiskCategory.PENDING_SETTLEMENT
        is_flagged = False
        reasons = [
            "Payment status is 'pending', awaiting bank or gateway settlement."
        ]
        summary = "Payment is pending settlement. Risk is moderate until completion or failure."
        recommended_action = "MONITOR_SETTLEMENT_STATUS"

    elif status_lower == "completed":
        risk_level = RiskLevel.LOW
        risk_score = 0.05
        category = RiskCategory.LOW_RISK_NORMAL
        is_flagged = False
        reasons = [
            "Payment status is 'completed' with no active dispute or failure indicators."
        ]
        summary = "Payment successfully completed with zero risk indicators."
        recommended_action = "NO_ACTION_REQUIRED"

    else:
        risk_level = RiskLevel.MEDIUM
        risk_score = 0.50
        category = RiskCategory.UNKNOWN_STATUS
        is_flagged = True
        reasons = [
            f"Payment status '{payment.status}' is unrecognized or ambiguous; specific cause cannot be inferred from available fields."
        ]
        summary = f"Unrecognized payment status '{payment.status}' encountered."
        recommended_action = "INSPECT_PAYMENT_RECORD"

    metadata = {
        "payment_status": payment.status,
        "amount": payment.amount,
        "currency": payment.currency,
        "customer_id": payment.customer_id,
        "merchant_id": payment.merchant_id,
        "description": payment.description,
        "retry_count": retry_count,
        "created_at": payment.created_at.isoformat() if payment.created_at else None
    }

    diagnosis = RiskDiagnosis(
        summary=summary,
        recommended_action=recommended_action,
        metadata=metadata
    )

    return RiskAssessmentResponse(
        payment_id=payment.id,
        risk_level=risk_level,
        risk_score=risk_score,
        category=category,
        is_flagged=is_flagged,
        reasons=reasons,
        diagnosis=diagnosis,
        evaluated_at=now
    )


def evaluate_checkout_risk(checkout: Any) -> RiskAssessmentResponse:
    """
    Deterministic evaluation path for CheckoutSession instances.
    Evaluates checkout abandonment risk using observed session attributes.
    """
    now = datetime.now(timezone.utc)
    status_upper = (getattr(checkout, "status", "") or "").upper()
    payment_attempted = getattr(checkout, "payment_attempted", False)
    retry_count = getattr(checkout, "retry_count", 0)

    if status_upper == "ABANDONED":
        risk_level = RiskLevel.MEDIUM
        risk_score = 0.50
        category = RiskCategory.CHECKOUT_ABANDONMENT
        is_flagged = True
        reasons = [
            "Customer initiated checkout session but did not complete payment within session timeout window."
        ]
        summary = "Checkout session abandoned prior to payment completion."
        recommended_action = "NUDGE_CUSTOMER_TO_RESUME_CHECKOUT"

    elif status_upper == "COMPLETED":
        risk_level = RiskLevel.LOW
        risk_score = 0.05
        category = RiskCategory.LOW_RISK_NORMAL
        is_flagged = False
        reasons = [
            "Checkout session was successfully completed with zero risk indicators."
        ]
        summary = "Checkout session successfully completed."
        recommended_action = "NO_ACTION_REQUIRED"

    elif status_upper == "STARTED":
        risk_level = RiskLevel.LOW
        risk_score = 0.20
        category = RiskCategory.PENDING_SETTLEMENT
        is_flagged = False
        reasons = [
            "Checkout session is currently active and within normal time limits."
        ]
        summary = "Checkout session in progress."
        recommended_action = "MONITOR_SETTLEMENT_STATUS"

    else:
        risk_level = RiskLevel.MEDIUM
        risk_score = 0.50
        category = RiskCategory.UNKNOWN_STATUS
        is_flagged = True
        reasons = [
            f"Checkout status '{status_upper}' is unrecognized."
        ]
        summary = f"Unrecognized checkout status '{status_upper}' encountered."
        recommended_action = "INSPECT_PAYMENT_RECORD"

    metadata = {
        "payment_status": status_upper,
        "amount": checkout.amount,
        "currency": checkout.currency,
        "customer_id": checkout.customer_id,
        "merchant_id": checkout.merchant_id,
        "description": checkout.description or "Checkout Session",
        "payment_attempted": payment_attempted,
        "retry_count": retry_count,
        "is_checkout_session": True,
        "created_at": checkout.created_at.isoformat() if getattr(checkout, "created_at", None) else None
    }

    diagnosis = RiskDiagnosis(
        summary=summary,
        recommended_action=recommended_action,
        metadata=metadata
    )

    return RiskAssessmentResponse(
        payment_id=checkout.id,
        risk_level=risk_level,
        risk_score=risk_score,
        category=category,
        is_flagged=is_flagged,
        reasons=reasons,
        diagnosis=diagnosis,
        evaluated_at=now
    )
