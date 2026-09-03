from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class CurrencyMetrics(BaseModel):
    currency: str = Field(..., description="Currency code (USD, EUR, GBP, CAD)")
    total_payments_evaluated: int = Field(..., description="Unique payments processed in this currency")
    total_revenue_at_risk: float = Field(..., description="Stable at-risk revenue from initial payment status")
    total_revenue_recovered: float = Field(..., description="Deduplicated revenue recovered")
    recovery_rate_percentage: float = Field(..., description="Percentage of at-risk revenue recovered")
    recovery_success_rate_percentage: float = Field(..., description="Percentage of at-risk payments recovered")
    human_escalation_rate_percentage: float = Field(..., description="Percentage of payments routed to human review")
    policy_block_rate_percentage: float = Field(..., description="Percentage of recommendations blocked by safety rules")
    
    successful_recoveries_count: int
    failed_recoveries_count: int
    blocked_cases_count: int
    escalated_cases_count: int
    monitored_cases_count: int
    no_action_cases_count: int

    class Config:
        from_attributes = True

class MetricsSummaryResponse(BaseModel):
    overall_payments_evaluated: int = Field(..., description="Total unique payments evaluated across all currencies")
    overall_human_escalation_rate_percentage: float = Field(..., description="Overall percentage of cases escalated")
    overall_policy_block_rate_percentage: float = Field(..., description="Overall percentage of cases blocked")
    by_currency: Dict[str, CurrencyMetrics] = Field(..., description="Metrics grouped by currency code")
    baseline_comparison: Optional[Dict[str, Any]] = Field(None, description="Optional side-by-side comparison vs Naive Always-Retry baseline")
    checkout_recovery_metrics: Optional[Dict[str, Any]] = Field(None, description="Separate checkout abandonment recovery metrics")
    generated_at: datetime

    class Config:
        from_attributes = True

class AuditLogEntryResponse(BaseModel):
    id: str
    payment_id: str
    amount: float
    currency: str
    customer_id: str
    merchant_id: str
    initial_payment_status: str
    new_payment_status: str
    
    # Complete Decision Chain
    risk_level: str
    risk_score: float
    risk_category: str
    risk_reasons: List[str]
    risk_diagnosis_action: str
    
    recommended_strategy: str
    action_type: str
    ai_explanation: str
    ai_confidence_score: float
    fallback_used: bool
    requires_human_escalation: bool
    suggested_customer_message: Optional[str] = None
    
    policy_decision: str
    policy_primary_reason: str
    policy_rules_evaluated: List[Dict[str, Any]]
    policy_violations: List[str]
    
    action_attempted: str
    workflow_outcome: str
    recovered_amount: float
    execution_logs: List[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True

class AuditLogListResponse(BaseModel):
    total: int
    logs: List[AuditLogEntryResponse]
