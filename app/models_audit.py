import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, Text, Boolean
from app.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, index=True)
    customer_id = Column(String, nullable=False)
    merchant_id = Column(String, nullable=False)
    initial_payment_status = Column(String, nullable=False)
    new_payment_status = Column(String, nullable=False)
    
    # Phase 2 Risk
    risk_level = Column(String, nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_category = Column(String, nullable=False)
    risk_reasons_json = Column(Text, nullable=False)
    risk_diagnosis_action = Column(String, nullable=False)
    
    # Phase 3 AI Recovery Agent
    recommended_strategy = Column(String, nullable=False)
    action_type = Column(String, nullable=False)
    ai_explanation = Column(Text, nullable=False)
    ai_confidence_score = Column(Float, nullable=False)
    fallback_used = Column(Boolean, nullable=False, default=True)
    requires_human_escalation = Column(Boolean, nullable=False, default=False)
    suggested_customer_message = Column(Text, nullable=True)
    
    # Phase 4 Policy Engine
    policy_decision = Column(String, nullable=False)
    policy_primary_reason = Column(Text, nullable=False)
    policy_rules_evaluated_json = Column(Text, nullable=False)
    policy_violations_json = Column(Text, nullable=False)
    
    # Phase 5 Workflow Simulation
    action_attempted = Column(String, nullable=False)
    workflow_outcome = Column(String, nullable=False)
    recovered_amount = Column(Float, nullable=False, default=0.0)
    execution_logs_json = Column(Text, nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
