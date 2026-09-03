from enum import Enum
from typing import List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class RiskCategory(str, Enum):
    DISPUTE_CHARGEBACK = "DISPUTE_CHARGEBACK"
    PAYMENT_FAILURE = "PAYMENT_FAILURE"
    CHECKOUT_ABANDONMENT = "CHECKOUT_ABANDONMENT"
    PENDING_SETTLEMENT = "PENDING_SETTLEMENT"
    LOW_RISK_NORMAL = "LOW_RISK_NORMAL"
    UNKNOWN_STATUS = "UNKNOWN_STATUS"

class RiskDiagnosis(BaseModel):
    summary: str
    recommended_action: str
    metadata: Dict[str, Any]

class RiskAssessmentResponse(BaseModel):
    payment_id: str
    risk_level: RiskLevel
    risk_score: float
    category: RiskCategory
    is_flagged: bool
    reasons: List[str]
    diagnosis: RiskDiagnosis
    evaluated_at: datetime

    class Config:
        from_attributes = True
