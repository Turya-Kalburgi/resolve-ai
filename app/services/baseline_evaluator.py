from typing import Dict, Any, List
from app.seed_demo import DEMO_SCENARIO_SPECS

def run_naive_baseline_evaluation() -> Dict[str, Any]:
    """
    Evaluates a deterministic Naive 'Always-Retry' Baseline strategy on the exact same
    30 synthetic payment scenario specifications without applying ResolveAI risk reasoning
    or policy safety gates.
    """
    by_currency: Dict[str, Dict[str, Any]] = {}
    
    total_evaluated = len(DEMO_SCENARIO_SPECS)
    total_retries_attempted = 0
    total_max_retry_violations_attempted = 0
    total_recovered_count = 0

    for spec in DEMO_SCENARIO_SPECS:
        curr = spec.get("currency", "USD")
        amount = float(spec.get("amount", 0.0))
        status = str(spec.get("status", "")).lower()
        retry_count = int(spec.get("retry_count", 0))
        simulate_success = bool(spec.get("simulate_success", True))

        if curr not in by_currency:
            by_currency[curr] = {
                "total_payments_evaluated": 0,
                "total_revenue_at_risk": 0.0,
                "retries_attempted": 0,
                "payments_recovered": 0,
                "revenue_recovered": 0.0,
                "recovery_rate_percentage": 0.0
            }

        curr_stats = by_currency[curr]
        curr_stats["total_payments_evaluated"] += 1

        if status in ["failed", "disputed", "pending"]:
            curr_stats["total_revenue_at_risk"] += amount

        # Naive Baseline Policy Logic:
        # Blindly attempts automated retry for any payment with status == "failed"
        if status == "failed":
            total_retries_attempted += 1
            curr_stats["retries_attempted"] += 1

            if retry_count >= 3:
                total_max_retry_violations_attempted += 1

            if simulate_success:
                total_recovered_count += 1
                curr_stats["payments_recovered"] += 1
                curr_stats["revenue_recovered"] += amount

    for curr, stats in by_currency.items():
        if stats["total_payments_evaluated"] > 0:
            stats["recovery_rate_percentage"] = round(
                (stats["payments_recovered"] / stats["total_payments_evaluated"]) * 100.0, 2
            )
            stats["revenue_recovered"] = round(stats["revenue_recovered"], 2)
            stats["total_revenue_at_risk"] = round(stats["total_revenue_at_risk"], 2)

    return {
        "strategy_name": "Naive Always-Retry Baseline",
        "governed_by_safety_policy": False,
        "total_payments_evaluated": total_evaluated,
        "retries_attempted": total_retries_attempted,
        "max_retry_limit_violations_attempted": total_max_retry_violations_attempted,
        "payments_recovered": total_recovered_count,
        "by_currency": by_currency
    }
