from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models_audit import AuditLog
from app.schemas_metrics import (
    MetricsSummaryResponse,
    AuditLogEntryResponse,
    AuditLogListResponse
)
from app.services.metrics_service import compute_metrics_summary, audit_model_to_schema

router = APIRouter(tags=["Metrics & Audit Trail"])

@router.get("/metrics/summary", response_model=MetricsSummaryResponse)
def get_metrics_summary(db: Session = Depends(get_db)):
    """
    Returns currency-segregated revenue recovery performance metrics across evaluated payments.
    Evaluates strictly unique payments processed through ResolveAI.
    """
    return compute_metrics_summary(db)

@router.get("/audit/logs", response_model=AuditLogListResponse)
def get_audit_logs(
    payment_id: Optional[str] = Query(None, description="Filter audit logs by payment_id"),
    outcome: Optional[str] = Query(None, description="Filter audit logs by workflow outcome (RECOVERED, FAILED, BLOCKED, etc.)"),
    policy_decision: Optional[str] = Query(None, description="Filter audit logs by policy decision (APPROVED, BLOCKED, ESCALATED)"),
    limit: int = Query(20, ge=1, le=100, description="Max audit logs to return"),
    offset: int = Query(0, ge=0, description="Number of audit logs to skip"),
    db: Session = Depends(get_db)
):
    """
    Returns a paginated list of audit trail records containing the complete decision chain.
    """
    query = db.query(AuditLog)
    if payment_id:
        query = query.filter(AuditLog.payment_id == payment_id)
    if outcome:
        query = query.filter(AuditLog.workflow_outcome == outcome)
    if policy_decision:
        query = query.filter(AuditLog.policy_decision == policy_decision)
        
    total = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    
    schema_logs = [audit_model_to_schema(entry) for entry in logs]
    return AuditLogListResponse(total=total, logs=schema_logs)

@router.get("/audit/logs/{payment_id}", response_model=AuditLogListResponse)
def get_audit_logs_for_payment(payment_id: str, db: Session = Depends(get_db)):
    """
    Returns complete audit history and decision traces for a specific payment ID.
    """
    logs = db.query(AuditLog).filter(AuditLog.payment_id == payment_id).order_by(AuditLog.created_at.desc()).all()
    if not logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit logs found for payment ID '{payment_id}'"
        )
    
    schema_logs = [audit_model_to_schema(entry) for entry in logs]
    return AuditLogListResponse(total=len(schema_logs), logs=schema_logs)
