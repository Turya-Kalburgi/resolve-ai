# ResolveAI — Master Project Specification

## 1. Overview & Project Goal
ResolveAI is an **AI-powered Revenue Recovery Agent for the Razorpay AI Buildathon**.

### Core Goals:
- **Detect revenue at risk** across payment transactions.
- **Diagnose payment situations** using deterministic risk and diagnostic rules.
- **Recommend recovery actions** via an AI reasoning agent.
- **Apply deterministic safety policies** to validate and gatekeep AI recommendations.
- **Simulate bounded recovery workflows** (using synthetic data; no real money movement).
- **Escalate when necessary** to human operators or specialized dispute teams.
- **Record decisions/actions** in a transparent audit trail.
- **Measure revenue recovered** across transaction batches.

---

## 2. Core User Story
As a merchant or finance operator, when payment failures, disputes, or settlement delays put revenue at risk, ResolveAI automatically inspects the transaction, evaluates the risk level, recommends a contextual recovery strategy via AI, validates it through safety policy rules, simulates bounded recovery workflows, and tracks total recovered revenue without requiring manual intervention for routine cases.

---

## 3. Important Safety Rules & Mandates
1. **Bounded Non-Execution in Early Phases**: The AI Recovery Agent only recommends strategies; it **NEVER** executes financial transactions directly.
2. **Safety Engine Gatekeeping**: All proposed AI recovery actions must pass through a deterministic Policy/Safety Engine before authorization.
3. **No Real Financial Transactions**: All recovery execution in this MVP is strictly simulated on synthetic data.
   - **No real money movement.**
   - **No real customer/payment data.**
   - **No real financial gateway execution.**
   - **Do not claim Razorpay integration** unless an actual documented integration is implemented.
4. **Mandatory Human Escalation**: High-risk dispute/chargeback scenarios and policy violations must be flagged for human review.

---

## 4. High-Level Architecture

```
Synthetic Payment Data
       ↓
Risk Detection Engine
       ↓
Diagnosis Engine
       ↓
AI Recovery Decision Agent
       ↓
Policy / Safety Engine
       ↓
Simulated Recovery Workflow
       ↓
Outcome
       ↓
Revenue Metrics + Audit Trail
       ↓
Dashboard
```

---

## 5. Technology Stack
- **Backend Framework**: Python 3.12, FastAPI 0.112+, Uvicorn 0.30+
- **Database & ORM**: SQLite, SQLAlchemy 2.0+
- **Data Validation & Schemas**: Pydantic v2 (2.8+)
- **HTTP Client**: HTTPX 0.28+
- **LLM Integration**: OpenAI/Gemini compatible JSON API via HTTPX with zero-dependency fallback heuristic engine.

---

## 6. Core Backend Modules & System Scope

### 1. Payment Service
Foundation service providing payment models (`id`, `amount`, `currency`, `status`, `customer_id`, `merchant_id`, `description`, `created_at`), pagination/filtering, and synthetic payment seeding.

### 2. Risk Detection & Diagnosis Engine
Evaluates payment attributes against deterministic rules to assign `RiskLevel` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), `RiskCategory` (`DISPUTE_CHARGEBACK`, `PAYMENT_FAILURE`, `PENDING_SETTLEMENT`, `LOW_RISK_NORMAL`, `UNKNOWN_STATUS`), and diagnostic metadata.

### 3. AI Recovery Decision Agent
Consumes structured risk assessment data and produces a structured `RecoveryRecommendationResponse` detailing `recommended_strategy`, `action_type`, `explanation`, `requires_human_escalation`, `suggested_customer_message`, and `confidence_score`. Supports LLM API and fallback heuristic execution.

### 4. Policy / Safety Engine (Phase 4 — NEXT)
Validates AI recommendations against predefined business & safety rules (e.g. maximum retry thresholds, dispute escalation rules, customer outreach constraints) before authorizing workflow execution.

### 5. Recovery Workflow Engine (Phase 5 — FUTURE)
Simulates approved recovery actions using synthetic data. Executes state transitions without moving real money or interacting with live financial gateways.

### 6. Audit & Metrics Service (Phase 6 — FUTURE)
Logs every risk evaluation, AI recommendation, policy decision, and simulated recovery outcome for auditability and revenue recovery performance tracking.

### 7. Dashboard (Phase 7 — FUTURE)
Interactive visual interface to monitor at-risk revenue, review AI recommendations, audit safety engine decisions, and track total recovered revenue.

---

## 7. Synthetic Dataset & Key Metrics

### Synthetic Dataset
25+ initial seed records covering `completed`, `failed`, `pending`, and `disputed` transaction states with realistic amounts, descriptions, customer IDs, and merchant IDs.

### Key Performance Metrics
- **Total Revenue at Risk ($)**
- **Total Revenue Recovered ($)**
- **Recovery Success Rate (%)**
- **Human Escalation Rate (%)**
- **Policy Engine Block / Rejection Rate (%)**

---

## 8. Implementation Roadmap & Current Status

- **Phase 1 — Core Payment API & Database Foundation** — ✅ **COMPLETED**
- **Phase 2 — Risk Detection & Diagnosis** — ✅ **COMPLETED**
- **Phase 3 — AI Recovery Agent** — ✅ **COMPLETED**
- **Phase 4 — Policy / Safety Engine** — ✅ **COMPLETED**
- **Phase 5 — Simulated Recovery Workflow** — ✅ **COMPLETED**
- **Phase 6 — Metrics & Audit Trail** — ✅ **COMPLETED**
- **Phase 7 — Judge-Facing Dashboard** — ✅ **COMPLETED**

---

## 📜 Completed Phases Specifications & Code Reference

### Phase 1: Core Payment API & Database Foundation (COMPLETED)
Phase 1 implements the foundational backend payment REST API.
- **FastAPI & Uvicorn Application**: [`app/main.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/main.py)
- **SQLite Database & SQLAlchemy ORM**: [`app/database.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/database.py), [`app/models.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/models.py)
- **Synthetic Generator**: [`app/seed.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/seed.py)
- **Endpoints**:
  - `GET /payments`: List payments with optional `status`, `customer_id`, `limit`, and `offset` filtering.
  - `GET /payments/{payment_id}`: Fetch single payment record by ID.

### Phase 2: AI / Risk Foundation (COMPLETED)
Phase 2 introduces the deterministic risk detection and diagnostic engine without modifying Phase 1 APIs.
- **Risk Schemas**: [`app/schemas_risk.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/schemas_risk.py) (`RiskLevel`, `RiskCategory`, `RiskDiagnosis`, `RiskAssessmentResponse`)
- **Deterministic Risk Engine**: [`app/services/risk_engine.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/services/risk_engine.py)
- **Endpoint**:
  - `GET /payments/{payment_id}/risk`: Evaluates and returns deterministic risk assessment and diagnosis.

### Phase 3: AI Recovery Agent (COMPLETED)
Phase 3 introduces the AI Recovery Agent to generate contextual recovery strategy recommendations.
- **Recovery Schemas**: [`app/schemas_recovery.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/schemas_recovery.py) (`RecoveryStrategy`, `RecoveryActionType`, `RecoveryRecommendationResponse`)
- **AI Recovery Agent Service**: [`app/services/recovery_agent.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/services/recovery_agent.py) (LLM reasoning + fallback heuristic rule engine)
- **Endpoint**:
  - `GET /payments/{payment_id}/recovery`: Evaluates risk and returns structured recovery recommendation.

### Phase 4: Policy / Safety Engine (COMPLETED)
Phase 4 introduces the deterministic Policy / Safety Engine to validate and gatekeep AI recovery recommendations before execution.
- **Policy Schemas**: [`app/schemas_policy.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/schemas_policy.py) (`PolicyDecision`, `PolicyRuleResult`, `PolicyEvaluationResponse`)
- **Policy Engine Service**: [`app/services/policy_engine.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/services/policy_engine.py) (100% deterministic rule engine evaluating completed status, max retries threshold, confidence threshold, dispute escalation, missing info, and disallowed action types)
- **Endpoint**:
  - `GET /payments/{payment_id}/policy`: Pipeline evaluating payment risk (Phase 2) $\rightarrow$ AI recovery strategy (Phase 3) $\rightarrow$ Policy safety decision (`APPROVED`, `BLOCKED`, `ESCALATED`) with optional `retry_count` query parameter.

### Phase 5: Simulated Recovery Workflow (COMPLETED)
Phase 5 introduces the Simulated Recovery Workflow Engine strictly gated by Policy Engine authorization. Performs bounded, synthetic recovery simulations with zero real money movement.
- **Workflow Schemas**: [`app/schemas_workflow.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/schemas_workflow.py) (`WorkflowOutcome`, `WorkflowStepLog`, `RecoveryWorkflowResponse`)
- **Workflow Engine Service**: [`app/services/workflow_engine.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/services/workflow_engine.py)
- **Endpoint**:
  - `POST /payments/{payment_id}/execute-recovery`: Pipeline evaluating payment risk (Phase 2) $\rightarrow$ AI recovery strategy (Phase 3) $\rightarrow$ Policy safety check (Phase 4) $\rightarrow$ Simulated Workflow Execution (Phase 5) producing `RECOVERED`, `FAILED`, `MONITORING`, `NO_ACTION`, `BLOCKED`, or `ESCALATED` outcomes.

### Phase 6: Metrics & Audit Trail (COMPLETED)
Phase 6 introduces complete observability, currency-segregated metrics aggregation, complete decision chain audit logging, and a 30-record synthetic batch evaluator.
- **Audit Model**: [`app/models_audit.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/models_audit.py) (`AuditLog`)
- **Metrics Schemas**: [`app/schemas_metrics.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/schemas_metrics.py) (`CurrencyMetrics`, `MetricsSummaryResponse`, `AuditLogEntryResponse`, `AuditLogListResponse`)
- **Metrics & Audit Service**: [`app/services/metrics_service.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/services/metrics_service.py) (deduplicated revenue accounting per unique payment ID, currency grouping, complete decision chain logging)
- **Synthetic Batch Evaluator**: [`app/seed_demo.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/seed_demo.py), [`app/services/batch_evaluator.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/services/batch_evaluator.py), [`app/evaluate_batch.py`](file:///Users/turyakalburgi/Developer/resolve-ai/app/evaluate_batch.py)
- **Endpoints**:
  - `GET /metrics/summary`: Currency-segregated performance metrics across evaluated unique payments.
  - `GET /audit/logs`: Paginated complete decision trace audit logs.
  - `GET /audit/logs/{payment_id}`: Decision history trace for a specific payment ID.
  - `POST /payments/evaluate-batch`: End-to-end evaluation runner across the 30-payment synthetic dataset.

