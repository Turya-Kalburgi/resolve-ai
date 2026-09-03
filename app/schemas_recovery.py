from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class RecoveryStrategy(str, Enum):
    CUSTOMER_RETRY_PROMPT = "CUSTOMER_RETRY_PROMPT"
    CHECKOUT_RECOVERY_NUDGE = "CHECKOUT_RECOVERY_NUDGE"
    HUMAN_DISPUTE_INVESTIGATION = "HUMAN_DISPUTE_INVESTIGATION"
    SETTLEMENT_MONITORING = "SETTLEMENT_MONITORING"
    NO_ACTION_COMPLETED = "NO_ACTION_COMPLETED"
    MANUAL_INSPECTION = "MANUAL_INSPECTION"

class RecoveryActionType(str, Enum):
    PROMPT_RETRY = "PROMPT_RETRY"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    STATUS_MONITOR = "STATUS_MONITOR"
    NO_OP = "NO_OP"

class RecoveryRecommendationResponse(BaseModel):
    payment_id: str = Field(..., description="ID of the evaluated payment")
    recommended_strategy: RecoveryStrategy = Field(..., description="High-level recovery strategy category")
    action_type: RecoveryActionType = Field(..., description="Standardized action type identifier for policy engine consumption")
    explanation: str = Field(..., description="Detailed contextual reasoning explaining why this strategy was recommended")
    requires_human_escalation: bool = Field(..., description="Flag indicating if human intervention/review is recommended")
    suggested_customer_message: Optional[str] = Field(None, description="Drafted customer communication message if applicable")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Agent confidence score in recommendation")
    fallback_used: bool = Field(default=False, description="True if fallback heuristic engine was used instead of LLM")
    generated_at: datetime = Field(..., description="Timestamp of recommendation generation")

    class Config:
        from_attributes = True
