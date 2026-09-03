import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import Payment
from app.models_audit import AuditLog
from app.schemas_risk import RiskAssessmentResponse
from app.schemas_recovery import RecoveryRecommendationResponse
from app.schemas_policy import PolicyEvaluationResponse
from app.schemas_workflow import RecoveryWorkflowResponse, WorkflowOutcome
from app.schemas_metrics import (
    CurrencyMetrics,
    MetricsSummaryResponse,
    AuditLogEntryResponse,
    AuditLogListResponse
)

def record_audit_log(
    db: Session,
    payment: Payment,
    initial_status: str,
    risk_assessment: RiskAssessmentResponse,
    recommendation: RecoveryRecommendationResponse,
    policy_evaluation: PolicyEvaluationResponse,
    workflow_response: RecoveryWorkflowResponse
) -> AuditLog:
    """
    Persists an immutable audit log entry containing the complete decision chain:
    Payment Snapshot -> Risk Diagnosis -> AI Recommendation -> Policy Evaluation -> Workflow Simulation.
    """
    audit_entry = AuditLog(
        payment_id=payment.id,
        amount=payment.amount,
        currency=payment.currency,
        customer_id=payment.customer_id,
        merchant_id=payment.merchant_id,
        initial_payment_status=initial_status,
        new_payment_status=workflow_response.new_payment_status,
        
        # Risk snapshot
        risk_level=risk_assessment.risk_level.value if hasattr(risk_assessment.risk_level, "value") else str(risk_assessment.risk_level),
        risk_score=risk_assessment.risk_score,
        risk_category=risk_assessment.category.value if hasattr(risk_assessment.category, "value") else str(risk_assessment.category),
        risk_reasons_json=json.dumps(risk_assessment.reasons),
        risk_diagnosis_action=risk_assessment.diagnosis.recommended_action,
        
        # AI Recovery Recommendation snapshot
        recommended_strategy=recommendation.recommended_strategy.value if hasattr(recommendation.recommended_strategy, "value") else str(recommendation.recommended_strategy),
        action_type=recommendation.action_type.value if hasattr(recommendation.action_type, "value") else str(recommendation.action_type),
        ai_explanation=recommendation.explanation,
        ai_confidence_score=recommendation.confidence_score,
        fallback_used=recommendation.fallback_used,
        requires_human_escalation=recommendation.requires_human_escalation,
        suggested_customer_message=recommendation.suggested_customer_message,
        
        # Policy Engine snapshot
        policy_decision=policy_evaluation.decision.value if hasattr(policy_evaluation.decision, "value") else str(policy_evaluation.decision),
        policy_primary_reason=policy_evaluation.primary_reason,
        policy_rules_evaluated_json=json.dumps([r.model_dump() for r in policy_evaluation.rules_evaluated], default=str),
        policy_violations_json=json.dumps(policy_evaluation.violations),
        
        # Workflow Simulation snapshot
        action_attempted=workflow_response.action_attempted,
        workflow_outcome=workflow_response.outcome.value if hasattr(workflow_response.outcome, "value") else str(workflow_response.outcome),
        recovered_amount=workflow_response.recovered_amount,
        execution_logs_json=json.dumps([l.model_dump() for l in workflow_response.execution_logs], default=str),
        
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    return audit_entry


def audit_model_to_schema(entry: AuditLog) -> AuditLogEntryResponse:
    """Helper converting AuditLog SQLAlchemy model to Pydantic AuditLogEntryResponse."""
    return AuditLogEntryResponse(
        id=entry.id,
        payment_id=entry.payment_id,
        amount=entry.amount,
        currency=entry.currency,
        customer_id=entry.customer_id,
        merchant_id=entry.merchant_id,
        initial_payment_status=entry.initial_payment_status,
        new_payment_status=entry.new_payment_status,
        risk_level=entry.risk_level,
        risk_score=entry.risk_score,
        risk_category=entry.risk_category,
        risk_reasons=json.loads(entry.risk_reasons_json or "[]"),
        risk_diagnosis_action=entry.risk_diagnosis_action,
        recommended_strategy=entry.recommended_strategy,
        action_type=entry.action_type,
        ai_explanation=entry.ai_explanation,
        ai_confidence_score=entry.ai_confidence_score,
        fallback_used=entry.fallback_used,
        requires_human_escalation=entry.requires_human_escalation,
        suggested_customer_message=entry.suggested_customer_message,
        policy_decision=entry.policy_decision,
        policy_primary_reason=entry.policy_primary_reason,
        policy_rules_evaluated=json.loads(entry.policy_rules_evaluated_json or "[]"),
        policy_violations=json.loads(entry.policy_violations_json or "[]"),
        action_attempted=entry.action_attempted,
        workflow_outcome=entry.workflow_outcome,
        recovered_amount=entry.recovered_amount,
        execution_logs=json.loads(entry.execution_logs_json or "[]"),
        created_at=entry.created_at
    )


def compute_metrics_summary(db: Session) -> MetricsSummaryResponse:
    """
    Computes deduplicated performance metrics grouped by currency.
    Scope: Strictly evaluates payments that have audit records in ResolveAI. Unprocessed payments are excluded.
    """
    now = datetime.now(timezone.utc)
    logs = db.query(AuditLog).order_by(AuditLog.created_at.asc()).all()
    
    if not logs:
        return MetricsSummaryResponse(
            overall_payments_evaluated=0,
            overall_human_escalation_rate_percentage=0.0,
            overall_policy_block_rate_percentage=0.0,
            by_currency={},
            generated_at=now
        )
    
    # Group audit entries by currency, then by payment_id (Filter out checkout sessions from payment benchmark)
    currency_groups: Dict[str, Dict[str, List[AuditLog]]] = {}
    for entry in logs:
        if entry.payment_id and entry.payment_id.startswith("chk_"):
            continue
        curr = entry.currency or "USD"
        if curr not in currency_groups:
            currency_groups[curr] = {}
        if entry.payment_id not in currency_groups[curr]:
            currency_groups[curr][entry.payment_id] = []
        currency_groups[curr][entry.payment_id].append(entry)

    # Separately aggregate checkout recovery metrics if checkout audit entries exist
    checkout_logs = [e for e in logs if e.payment_id and e.payment_id.startswith("chk_")]
    checkout_metrics = None
    if checkout_logs:
        chk_groups: Dict[str, Dict[str, List[AuditLog]]] = {}
        for entry in checkout_logs:
            c = entry.currency or "USD"
            if c not in chk_groups:
                chk_groups[c] = {}
            if entry.payment_id not in chk_groups[c]:
                chk_groups[c][entry.payment_id] = []
            chk_groups[c][entry.payment_id].append(entry)

        chk_by_currency = {}
        for c, pdict in chk_groups.items():
            tot_sess = len(pdict)
            at_risk = sum(pdict[pid][0].amount for pid in pdict if pdict[pid][0].initial_payment_status == "ABANDONED")
            rec_amt = sum(pdict[pid][-1].recovered_amount for pid in pdict if pdict[pid][-1].workflow_outcome == "RECOVERED")
            chk_by_currency[c] = {
                "total_checkout_sessions": tot_sess,
                "revenue_at_risk": round(at_risk, 2),
                "revenue_recovered": round(rec_amt, 2),
                "recovery_rate_percentage": round((rec_amt / at_risk * 100.0), 2) if at_risk > 0 else 0.0
            }
        checkout_metrics = {
            "total_checkout_sessions": len(set(e.payment_id for e in checkout_logs)),
            "by_currency": chk_by_currency
        }
        
    by_currency: Dict[str, CurrencyMetrics] = {}
    total_evaluated_all = 0
    total_escalated_all = 0
    total_blocked_all = 0
    
    for curr, payment_dict in currency_groups.items():
        total_eval = len(payment_dict)
        total_evaluated_all += total_eval
        
        at_risk_amount = 0.0
        recovered_amount = 0.0
        at_risk_count = 0
        
        succ_count = 0
        failed_count = 0
        blocked_count = 0
        escalated_count = 0
        monitored_count = 0
        no_action_count = 0
        
        for pid, entries in payment_dict.items():
            first_entry = entries[0]
            latest_entry = entries[-1]
            
            orig_amount = first_entry.amount
            init_status = (first_entry.initial_payment_status or "").lower()
            
            # Stable revenue at risk based on initial snapshot
            is_at_risk = init_status in ["failed", "disputed"]
            if is_at_risk:
                at_risk_amount += orig_amount
                at_risk_count += 1
                
            # Check if ever recovered
            ever_recovered = any(e.workflow_outcome == WorkflowOutcome.RECOVERED.value and e.recovered_amount > 0 for e in entries)
            
            if ever_recovered:
                recovered_amount += orig_amount
                succ_count += 1
            else:
                # Classify based on latest outcome
                outcome = latest_entry.workflow_outcome
                if outcome == WorkflowOutcome.BLOCKED.value:
                    blocked_count += 1
                elif outcome == WorkflowOutcome.ESCALATED.value:
                    escalated_count += 1
                elif outcome == WorkflowOutcome.FAILED.value:
                    failed_count += 1
                elif outcome == WorkflowOutcome.MONITORING.value:
                    monitored_count += 1
                else:
                    no_action_count += 1

        total_blocked_all += blocked_count
        total_escalated_all += escalated_count

        recovery_rate = round((recovered_amount / at_risk_amount * 100.0), 2) if at_risk_amount > 0 else 0.0
        success_rate = round((succ_count / at_risk_count * 100.0), 2) if at_risk_count > 0 else 0.0
        escalation_rate = round((escalated_count / total_eval * 100.0), 2) if total_eval > 0 else 0.0
        block_rate = round((blocked_count / total_eval * 100.0), 2) if total_eval > 0 else 0.0

        by_currency[curr] = CurrencyMetrics(
            currency=curr,
            total_payments_evaluated=total_eval,
            total_revenue_at_risk=round(at_risk_amount, 2),
            total_revenue_recovered=round(recovered_amount, 2),
            recovery_rate_percentage=recovery_rate,
            recovery_success_rate_percentage=success_rate,
            human_escalation_rate_percentage=escalation_rate,
            policy_block_rate_percentage=block_rate,
            successful_recoveries_count=succ_count,
            failed_recoveries_count=failed_count,
            blocked_cases_count=blocked_count,
            escalated_cases_count=escalated_count,
            monitored_cases_count=monitored_count,
            no_action_cases_count=no_action_count
        )

    overall_esc_rate = round((total_escalated_all / total_evaluated_all * 100.0), 2) if total_evaluated_all > 0 else 0.0
    overall_blk_rate = round((total_blocked_all / total_evaluated_all * 100.0), 2) if total_evaluated_all > 0 else 0.0

    from app.services.baseline_evaluator import run_naive_baseline_evaluation
    baseline_res = run_naive_baseline_evaluation()

    baseline_comp = {
        "strategy": "Naive Always-Retry Baseline",
        "governed_by_policy": False,
        "total_evaluated": baseline_res["total_payments_evaluated"],
        "baseline_retries_attempted": baseline_res["retries_attempted"],
        "baseline_max_retry_violations_attempted": baseline_res["max_retry_limit_violations_attempted"],
        "baseline_payments_recovered": baseline_res["payments_recovered"],
        "baseline_by_currency": baseline_res["by_currency"],
        "resolveai_comparison": {
            "total_evaluated": total_evaluated_all,
            "resolveai_blocked_actions": total_blocked_all,
            "resolveai_escalated_actions": total_escalated_all,
            "max_retry_limit_violations_avoided": baseline_res["max_retry_limit_violations_attempted"],
            "financial_side_effects_in_resolveai": 0
        }
    }

    return MetricsSummaryResponse(
        overall_payments_evaluated=total_evaluated_all,
        overall_human_escalation_rate_percentage=overall_esc_rate,
        overall_policy_block_rate_percentage=overall_blk_rate,
        by_currency=by_currency,
        baseline_comparison=baseline_comp,
        checkout_recovery_metrics=checkout_metrics,
        generated_at=now
    )
