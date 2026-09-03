from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class PolicyDecision(str, Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"

class PolicyRuleResult(BaseModel):
    rule_id: str = Field(..., description="Unique identifier code for policy rule")
    rule_name: str = Field(..., description="Human-readable rule title")
    passed: bool = Field(..., description="True if rule passed, False if violated or triggered escalation")
    severity: str = Field(..., description="Severity level: INFO, BLOCK, or ESCALATE")
    message: str = Field(..., description="Detailed explanation of rule evaluation result")

class PolicyEvaluationResponse(BaseModel):
    payment_id: str = Field(..., description="ID of payment evaluated")
    decision: PolicyDecision = Field(..., description="Final policy decision: APPROVED, BLOCKED, or ESCALATED")
    recommended_action: str = Field(..., description="The action proposed by AI Recovery Agent")
    primary_reason: str = Field(..., description="Summary explanation of policy evaluation outcome")
    rules_evaluated: List[PolicyRuleResult] = Field(..., description="Individual results for each safety rule evaluated")
    violations: List[str] = Field(default_factory=list, description="List of specific rule violation messages if blocked or escalated")
    evaluated_at: datetime = Field(..., description="Timestamp of evaluation")

    class Config:
        from_attributes = True
