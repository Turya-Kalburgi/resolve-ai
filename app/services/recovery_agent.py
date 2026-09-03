import os
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import httpx
from app.schemas_risk import RiskAssessmentResponse, RiskCategory, RiskLevel
from app.schemas_recovery import (
    RecoveryRecommendationResponse,
    RecoveryStrategy,
    RecoveryActionType
)

HIGH_VALUE_THRESHOLDS: Dict[str, float] = {
    "USD": 300.00,
    "EUR": 250.00,
    "GBP": 200.00,
    "CAD": 400.00,
}

def _classify_intent(description: str) -> Tuple[str, float]:
    desc_lower = (description or "").lower()
    if any(k in desc_lower for k in ["subscription", "renewal", "tier upgrade"]):
        return "RECURRING_SUBSCRIPTION", 0.02
    elif any(k in desc_lower for k in ["enterprise", "monthly billing", "invoice"]):
        return "ENTERPRISE_BILLING", 0.03
    elif any(k in desc_lower for k in ["checkout", "order", "purchase", "top-up", "credit", "addon", "download"]):
        return "ONE_TIME_CHECKOUT", 0.00
    else:
        return "UNKNOWN_INTENT", -0.05

def _fallback_heuristic_recommendation(risk_assessment: RiskAssessmentResponse) -> RecoveryRecommendationResponse:
    """
    Multi-signal contextual deterministic recovery recommendation engine used as a fallback
    or default strategy when LLM integration is disabled or unavailable.
    """
    now = datetime.now(timezone.utc)
    category = risk_assessment.category
    risk_level = risk_assessment.risk_level
    metadata = risk_assessment.diagnosis.metadata or {}
    
    amount_val = metadata.get("amount", 0.0)
    try:
        amount = float(amount_val)
    except (ValueError, TypeError):
        amount = 0.0

    currency = str(metadata.get("currency", "USD")).upper()
    description = str(metadata.get("description", "your transaction"))
    status_lower = str(metadata.get("payment_status", "")).lower()

    # Currency-aware High Value Tier calculation
    hv_threshold = HIGH_VALUE_THRESHOLDS.get(currency, 300.00)
    is_high_value = amount > hv_threshold
    tier_label = "High-Value Tier" if is_high_value else "Standard Tier"
    hv_adj = -0.05 if is_high_value else 0.00

    # Intent Classification
    intent, intent_modifier = _classify_intent(description)

    # Ambiguity Adjustment
    is_ambiguous = category == RiskCategory.UNKNOWN_STATUS or status_lower == "declined_unknown"
    ambiguity_adj = -0.05 if is_ambiguous else 0.00

    amount_str = f"{amount:.2f} {currency}" if amount > 0 else f"{currency}"
    reasons_str = "; ".join(risk_assessment.reasons) if risk_assessment.reasons else "None"

    retry_count = int(metadata.get("retry_count", 0))
    is_checkout = metadata.get("is_checkout_session", False)
    payment_attempted = bool(metadata.get("payment_attempted", False))

    if category == RiskCategory.CHECKOUT_ABANDONMENT:
        if retry_count >= 3:
            base_confidence = 0.85
            strategy = RecoveryStrategy.CHECKOUT_RECOVERY_NUDGE
            action_type = RecoveryActionType.PROMPT_RETRY
            requires_human_escalation = False
            inference_str = f"Maximum reminder threshold reached ({retry_count} prior attempts) for an abandoned checkout session"
            justification_str = "prompt customer checkout nudge (subject to safety policy threshold)"
            suggested_message = None
        else:
            base_confidence = 0.88
            strategy = RecoveryStrategy.CHECKOUT_RECOVERY_NUDGE
            action_type = RecoveryActionType.PROMPT_RETRY
            requires_human_escalation = False
            if not payment_attempted:
                inference_str = "The checkout session ended before a payment attempt was recorded; a gentle checkout recovery nudge is appropriate"
            else:
                inference_str = "The checkout session was abandoned after an initial payment attempt; a checkout recovery nudge is appropriate"
            justification_str = "prompt customer to resume checkout session and complete purchase"
            suggested_message = (
                f"You left items in your checkout of {amount_str} for '{description}'. "
                "Click here to resume checkout and complete your order."
            )

    elif category == RiskCategory.DISPUTE_CHARGEBACK or risk_level == RiskLevel.CRITICAL:
        base_confidence = 0.95
        strategy = RecoveryStrategy.HUMAN_DISPUTE_INVESTIGATION
        action_type = RecoveryActionType.HUMAN_REVIEW
        requires_human_escalation = True
        inference_str = "Payment status is currently marked as disputed by active customer chargeback"
        justification_str = "collect dispute evidence and coordinate mandatory human bank review"
        suggested_message = (
            f"Your payment of {amount_str} is currently under dispute review. "
            "Our support team will contact you shortly."
        )

    elif category == RiskCategory.PAYMENT_FAILURE or risk_level == RiskLevel.HIGH:
        if retry_count >= 3:
            base_confidence = 0.85
            strategy = RecoveryStrategy.MANUAL_INSPECTION
            action_type = RecoveryActionType.HUMAN_REVIEW
            requires_human_escalation = True
            inference_str = f"Maximum retry threshold reached ({retry_count} prior attempts); automated retries should not be attempted further"
            justification_str = "evaluate manual account intervention"
            suggested_message = None
        else:
            base_confidence = 0.90
            strategy = RecoveryStrategy.CUSTOMER_RETRY_PROMPT
            action_type = RecoveryActionType.PROMPT_RETRY
            requires_human_escalation = False
            if intent == "RECURRING_SUBSCRIPTION":
                inference_str = "Recurring subscription renewal failure detected; prompt customer retry is appropriate for subscription billing continuity"
                justification_str = "prompt customer to re-attempt payment or update subscription billing details"
            else:
                inference_str = "Transaction processing failed for a standard checkout payment"
                justification_str = "prompt customer to re-attempt payment or update billing details"
            suggested_message = (
                f"We were unable to process your payment of {amount_str} for '{description}'. "
                "Please check your billing details and try again."
            )

    elif category == RiskCategory.PENDING_SETTLEMENT:
        base_confidence = 0.85
        strategy = RecoveryStrategy.SETTLEMENT_MONITORING
        action_type = RecoveryActionType.STATUS_MONITOR
        requires_human_escalation = False
        inference_str = "Payment status is currently marked as pending settlement"
        justification_str = "monitor transaction status until settlement or failure is confirmed"
        suggested_message = None

    elif category == RiskCategory.LOW_RISK_NORMAL or risk_level == RiskLevel.LOW:
        base_confidence = 1.00
        strategy = RecoveryStrategy.NO_ACTION_COMPLETED
        action_type = RecoveryActionType.NO_OP
        requires_human_escalation = False
        inference_str = "Payment status is currently marked as completed"
        justification_str = "verify zero intervention is required"
        suggested_message = None

    else:
        base_confidence = 0.70
        strategy = RecoveryStrategy.MANUAL_INSPECTION
        action_type = RecoveryActionType.HUMAN_REVIEW
        requires_human_escalation = True
        inference_str = "Available transaction evidence is insufficient to determine specific failure cause; status is ambiguous"
        justification_str = "trigger manual inspection of payment logs by finance team"
        suggested_message = None

    # Calculate exact clamped confidence score
    raw_confidence = base_confidence + intent_modifier + hv_adj + ambiguity_adj
    confidence = round(min(max(raw_confidence, 0.0), 1.0), 2)

    # Construct strict 3-part evidence-based explanation format
    if is_checkout:
        explanation = (
            f"OBSERVED FACTS: Checkout {risk_assessment.payment_id} is '{status_lower}', "
            f"amount is {amount_str} ({tier_label}), payment_attempted is {str(payment_attempted).lower()}, and risk category {category.value if hasattr(category, 'value') else category} "
            f"(Reasons: {reasons_str}).\n"
            f"INFERENCE: {inference_str}.\n"
            f"RECOMMENDATION: Propose {strategy.value if hasattr(strategy, 'value') else strategy} "
            f"via {action_type.value if hasattr(action_type, 'value') else action_type} "
            f"with calibrated confidence {confidence:.2f} to {justification_str}."
        )
    else:
        explanation = (
            f"OBSERVED FACTS: Payment {risk_assessment.payment_id} has status '{status_lower}', "
            f"amount {amount_str} ({tier_label}), intent '{intent}', retry count {retry_count}, and risk category {category.value if hasattr(category, 'value') else category} "
            f"(Reasons: {reasons_str}).\n"
            f"INFERENCE: {inference_str}.\n"
            f"RECOMMENDATION: Propose {strategy.value if hasattr(strategy, 'value') else strategy} "
            f"via {action_type.value if hasattr(action_type, 'value') else action_type} "
            f"with calibrated confidence {confidence:.2f} to {justification_str}."
        )

    return RecoveryRecommendationResponse(
        payment_id=risk_assessment.payment_id,
        recommended_strategy=strategy,
        action_type=action_type,
        explanation=explanation,
        requires_human_escalation=requires_human_escalation,
        suggested_customer_message=suggested_message,
        confidence_score=confidence,
        fallback_used=True,
        generated_at=now
    )


def _call_llm_recovery_agent(risk_assessment: RiskAssessmentResponse) -> Optional[RecoveryRecommendationResponse]:
    """
    Invokes external LLM API to reason about risk diagnosis and generate structured JSON recommendation.
    Strictly validates output schema and action types; falls back to deterministic engine on any failure.
    """
    provider = os.getenv("LLM_PROVIDER", "none").lower()
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    timeout_sec = float(os.getenv("LLM_TIMEOUT", "5.0"))

    if provider == "none" or not api_key:
        return None

    prompt = (
        "You are an AI Payment Recovery Agent. Analyze the following risk assessment and output JSON ONLY.\n"
        f"Payment ID: {risk_assessment.payment_id}\n"
        f"Risk Level: {risk_assessment.risk_level.value if hasattr(risk_assessment.risk_level, 'value') else risk_assessment.risk_level}\n"
        f"Risk Score: {risk_assessment.risk_score}\n"
        f"Category: {risk_assessment.category.value if hasattr(risk_assessment.category, 'value') else risk_assessment.category}\n"
        f"Reasons: {', '.join(risk_assessment.reasons)}\n"
        f"Diagnosis Summary: {risk_assessment.diagnosis.summary}\n"
        f"Diagnosis Recommended Action: {risk_assessment.diagnosis.recommended_action}\n"
        f"Metadata: {json.dumps(risk_assessment.diagnosis.metadata or {})}\n\n"
        "Return JSON with keys: recommended_strategy, action_type, explanation, requires_human_escalation, suggested_customer_message, confidence_score.\n"
        "Valid strategies: CUSTOMER_RETRY_PROMPT, HUMAN_DISPUTE_INVESTIGATION, SETTLEMENT_MONITORING, NO_ACTION_COMPLETED, MANUAL_INSPECTION.\n"
        "Valid action_types: PROMPT_RETRY, HUMAN_REVIEW, STATUS_MONITOR, NO_OP."
    )

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        url = os.getenv("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a specialized payment recovery strategy AI. Respond strictly in valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }

        with httpx.Client(timeout=timeout_sec) as client:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                parsed = json.loads(content)

                # Strict validation of required keys
                required_keys = ["recommended_strategy", "action_type", "explanation", "requires_human_escalation", "confidence_score"]
                if not all(k in parsed for k in required_keys):
                    return None

                # Strict enum validation
                rec_strategy = RecoveryStrategy(parsed["recommended_strategy"])
                rec_action = RecoveryActionType(parsed["action_type"])

                return RecoveryRecommendationResponse(
                    payment_id=risk_assessment.payment_id,
                    recommended_strategy=rec_strategy,
                    action_type=rec_action,
                    explanation=str(parsed["explanation"]),
                    requires_human_escalation=bool(parsed["requires_human_escalation"]),
                    suggested_customer_message=parsed.get("suggested_customer_message"),
                    confidence_score=float(parsed.get("confidence_score", 0.9)),
                    fallback_used=False,
                    generated_at=datetime.now(timezone.utc)
                )
    except Exception:
        # Gracefully handle network timeouts, parsing errors, invalid enums, or rate limits
        return None

    return None


def generate_recovery_recommendation(risk_assessment: RiskAssessmentResponse) -> RecoveryRecommendationResponse:
    """
    Main entrypoint for Phase 3 AI Recovery Agent.
    Attempts LLM resolution first; falls back to multi-signal deterministic engine.
    Guaranteed to produce a valid RecoveryRecommendationResponse without executing financial actions.
    """
    llm_response = _call_llm_recovery_agent(risk_assessment)
    if llm_response:
        return llm_response
    
    return _fallback_heuristic_recommendation(risk_assessment)
