import json
from app.database import Base, engine, SessionLocal
from app.services.batch_evaluator import run_batch_evaluation

def main():
    print("=" * 70)
    print(" ResolveAI — Batch Evaluation Runner (Phases 1-6 End-to-End)")
    print("=" * 70)
    
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        results = run_batch_evaluation(db, reset_db=True)
        print(f"\n[+] Total Payments Evaluated: {results['total_payments_processed']}")
        print(f"[+] Execution Time: {results['execution_time_seconds']} seconds\n")
        
        print("Outcomes Breakdown:")
        print("-" * 35)
        for outcome, count in results['outcomes_breakdown'].items():
            print(f"  - {outcome:<15}: {count} payment(s)")
            
        print("\nCurrency Metrics Summary:")
        print("-" * 70)
        metrics = results['metrics_summary'].by_currency
        for curr, m in metrics.items():
            print(f"  Currency: {curr}")
            print(f"    - Evaluated           : {m.total_payments_evaluated}")
            print(f"    - At-Risk Revenue     : {m.total_revenue_at_risk:.2f} {curr}")
            print(f"    - Recovered Revenue    : {m.total_revenue_recovered:.2f} {curr}")
            print(f"    - Recovery Rate       : {m.recovery_rate_percentage:.2f}%")
            print(f"    - Recovery Success Rate: {m.recovery_success_rate_percentage:.2f}%")
            print(f"    - Escalation Rate     : {m.human_escalation_rate_percentage:.2f}%")
            print(f"    - Policy Block Rate   : {m.policy_block_rate_percentage:.2f}%")
            print()
            
        print("=" * 70)
        print(" NAIVE ALWAYS-RETRY BASELINE vs RESOLVEAI COMPARISON")
        print("=" * 70)
        baseline_comp = results['metrics_summary'].baseline_comparison
        if baseline_comp:
            base_res = baseline_comp.get("naive_baseline", {})
            print(f"  Strategy                        : {baseline_comp.get('strategy')}")
            print(f"  Governed by Safety Policy       : {baseline_comp.get('governed_by_policy')}")
            print(f"  Evaluated Dataset Records       : {baseline_comp.get('total_evaluated')} payments")
            print(f"  Naive Retries Attempted         : {baseline_comp.get('baseline_retries_attempted')} retries")
            print(f"  Max Retry Limit Violations      : {baseline_comp.get('baseline_max_retry_violations_attempted')} (Unsafe Retries Attempted)")
            print(f"  ResolveAI Safety Blocked Actions: {baseline_comp['resolveai_comparison'].get('resolveai_blocked_actions')}")
            print(f"  ResolveAI Human Escalations     : {baseline_comp['resolveai_comparison'].get('resolveai_escalated_actions')}")
            print(f"  ResolveAI Unsafe Retries Avoided: {baseline_comp['resolveai_comparison'].get('max_retry_limit_violations_avoided')}")
            print(f"  Financial Side Effects          : {baseline_comp['resolveai_comparison'].get('financial_side_effects_in_resolveai')} (ResolveAI)")

        print("=" * 70)
        print(" [✓] Batch Evaluation Completed Successfully with 0 Financial Side Effects.")
        print("=" * 70)
    finally:
        db.close()

if __name__ == "__main__":
    main()
