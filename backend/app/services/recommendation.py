"""Transparent, rule-based cost simulation across insurance plans.

Assumptions (unit costs) are rough national averages for a "typical" allowed
amount per service — they are estimates, not a substitute for actual insurer
pricing, and are surfaced to the user so the math is auditable rather than a
black box.
"""

from __future__ import annotations

import json
from pathlib import Path

PLANS_PATH = Path(__file__).resolve().parent.parent / "data" / "plans.json"

UNIT_COSTS = {
    "primary_care_visit": 150,
    "specialist_visit": 250,
    "er_visit": 1800,
    "generic_rx_fill": 25,
    "brand_rx_fill": 180,
}

# A large unplanned event added to the "worst case" projection so plans can
# be compared on downside risk, not just expected cost.
WORST_CASE_SHOCK = 25000
BEST_CASE_UTILIZATION_FACTOR = 0.5


def load_plans() -> list[dict]:
    with open(PLANS_PATH) as f:
        return json.load(f)


def _apply_deductible_coinsurance(
    allowed: float, deductible_remaining: float, oop_remaining: float, coinsurance: float
) -> tuple[float, float, float]:
    """Returns (patient_pays, new_deductible_remaining, new_oop_remaining)."""
    if oop_remaining <= 0 or allowed <= 0:
        return 0.0, deductible_remaining, oop_remaining

    deduct_portion = min(allowed, deductible_remaining)
    coinsurance_portion = allowed - deduct_portion
    patient_pays = deduct_portion + coinsurance_portion * coinsurance
    patient_pays = min(patient_pays, oop_remaining)

    return patient_pays, deductible_remaining - deduct_portion, oop_remaining - patient_pays


def _apply_copay(copay: float, oop_remaining: float) -> tuple[float, float]:
    """Returns (patient_pays, new_oop_remaining). Copays count toward OOP max
    but not toward the deductible (standard for copay-style plans)."""
    patient_pays = min(copay, oop_remaining) if oop_remaining > 0 else 0.0
    return patient_pays, max(oop_remaining - patient_pays, 0)


def simulate_plan_cost(plan: dict, utilization: dict, extra_shock: float = 0.0) -> dict:
    """Simulate one family's annual cost on one plan given a utilization profile.

    utilization keys: primary_care_visits, specialist_visits, er_visits,
    generic_prescriptions, brand_prescriptions, planned_procedure_cost
    """
    deductible_remaining = plan["deductible_family"]
    oop_remaining = plan["oop_max_family"]
    coinsurance = plan["coinsurance"]
    uses_copays = plan["uses_copays"]
    breakdown: dict[str, float] = {}

    def bill(label: str, count: float, unit_cost: float, copay_key: str | None):
        nonlocal deductible_remaining, oop_remaining
        if count <= 0:
            return
        total_patient = 0.0
        for _ in range(int(round(count))):
            if uses_copays and copay_key and plan.get(copay_key) is not None:
                paid, oop_remaining = _apply_copay(plan[copay_key], oop_remaining)
            else:
                paid, deductible_remaining, oop_remaining = _apply_deductible_coinsurance(
                    unit_cost, deductible_remaining, oop_remaining, coinsurance
                )
            total_patient += paid
        breakdown[label] = round(total_patient, 2)

    bill(
        "primary_care",
        utilization.get("primary_care_visits", 0),
        UNIT_COSTS["primary_care_visit"],
        "primary_care_copay",
    )
    bill(
        "specialist",
        utilization.get("specialist_visits", 0),
        UNIT_COSTS["specialist_visit"],
        "specialist_copay",
    )
    bill("er", utilization.get("er_visits", 0), UNIT_COSTS["er_visit"], "er_copay")
    bill(
        "generic_prescriptions",
        utilization.get("generic_prescriptions", 0),
        UNIT_COSTS["generic_rx_fill"],
        "generic_rx_copay",
    )
    bill(
        "brand_prescriptions",
        utilization.get("brand_prescriptions", 0),
        UNIT_COSTS["brand_rx_fill"],
        "brand_rx_copay",
    )

    # Planned procedures and any "worst case" shock always run through
    # deductible + coinsurance (copays don't apply to major procedures).
    procedure_cost = utilization.get("planned_procedure_cost", 0) + extra_shock
    if procedure_cost > 0:
        paid, deductible_remaining, oop_remaining = _apply_deductible_coinsurance(
            procedure_cost, deductible_remaining, oop_remaining, coinsurance
        )
        breakdown["major_procedures_or_events"] = round(paid, 2)

    out_of_pocket = round(sum(breakdown.values()), 2)
    annual_premium = round(plan["monthly_premium_family"] * 12, 2)

    return {
        "out_of_pocket": out_of_pocket,
        "annual_premium": annual_premium,
        "total_cost": round(out_of_pocket + annual_premium, 2),
        "breakdown": breakdown,
    }


def build_recommendation(utilization: dict) -> list[dict]:
    plans = load_plans()
    results = []

    best_case_utilization = {
        k: (v * BEST_CASE_UTILIZATION_FACTOR if k != "planned_procedure_cost" else v)
        for k, v in utilization.items()
    }

    for plan in plans:
        expected = simulate_plan_cost(plan, utilization)
        best_case = simulate_plan_cost(plan, best_case_utilization)
        worst_case = simulate_plan_cost(plan, utilization, extra_shock=WORST_CASE_SHOCK)

        results.append(
            {
                "plan_id": plan["id"],
                "plan_name": plan["name"],
                "plan_type": plan["type"],
                "annual_premium": expected["annual_premium"],
                "expected_out_of_pocket": expected["out_of_pocket"],
                "expected_total_cost": expected["total_cost"],
                "best_case_total_cost": best_case["total_cost"],
                "worst_case_total_cost": worst_case["total_cost"],
                "breakdown": expected["breakdown"],
                "notes": plan["notes"],
                "requires_referral": plan["requires_referral"],
                "out_of_network_coverage": plan["out_of_network_coverage"],
            }
        )

    return results


def pick_recommended_plan(results: list[dict]) -> str:
    """Lowest expected total cost wins, unless another plan is within 5% of
    the cheapest expected cost but meaningfully protects against a bad year
    (much lower worst-case cost) — then favor the more protective plan."""
    by_expected = sorted(results, key=lambda r: r["expected_total_cost"])
    cheapest = by_expected[0]
    threshold = cheapest["expected_total_cost"] * 1.05

    close_contenders = [r for r in by_expected if r["expected_total_cost"] <= threshold]
    best_protection = min(close_contenders, key=lambda r: r["worst_case_total_cost"])

    if best_protection["worst_case_total_cost"] < cheapest["worst_case_total_cost"] * 0.85:
        return best_protection["plan_id"]
    return cheapest["plan_id"]
