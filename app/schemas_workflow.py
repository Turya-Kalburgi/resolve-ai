from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class WorkflowOutcome(str, Enum):
    RECOVERED = "RECOVERED"
    FAILED = "FAILED"
    MONITORING = "MONITORING"
    NO_ACTION = "NO_ACTION"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"

class WorkflowStepLog(BaseModel):
    step_number: int
    step_name: str
    status: str
    details: str
    timestamp: datetime

class RecoveryWorkflowResponse(BaseModel):
    payment_id: str = Field(..., description="ID of payment evaluated")
    outcome: WorkflowOutcome = Field(..., description="Final workflow outcome: RECOVERED, FAILED, MONITORING, NO_ACTION, BLOCKED, ESCALATED")
    policy_decision: str = Field(..., description="Policy decision: APPROVED, BLOCKED, ESCALATED")
    action_attempted: str = Field(..., description="Action attempted by workflow engine")
    recovered_amount: float = Field(..., description="Amount recovered in simulation (only > 0.0 when active recovery succeeds)")
    currency: str = Field(..., description="Transaction currency")
    previous_payment_status: str = Field(..., description="Status before workflow execution")
    new_payment_status: str = Field(..., description="Status after workflow execution")
    execution_logs: List[WorkflowStepLog] = Field(..., description="Step-by-step execution audit log")
    executed_at: datetime = Field(..., description="Execution timestamp")

    class Config:
        from_attributes = True
