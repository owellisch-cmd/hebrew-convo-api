"""Transparent, rule-based cost simulation across insurance plans.

Assumptions (unit costs) are rough national averages for a "typical" allowed
amount per service — they are estimates, not a substitute for actual insurer
pricing, and are surfaced to the user so the math is auditable rather than a
black box.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.pathways import evaluate_plan_access

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


# How a pathway service is billed. None means it runs through deductible +
# coinsurance rather than a flat copay.
SERVICE_TYPE_COPAY_KEY = {
    "primary_care": "primary_care_copay",
    "specialist": "specialist_copay",
    "physical_therapy": "therapy_copay",
    "occupational_therapy": "therapy_copay",
    "imaging": None,
    "advanced_imaging": None,
    "procedure": None,
    "prescription": "generic_rx_copay",
}


def simulate_plan_cost(
    plan: dict,
    utilization: dict,
    extra_shock: float = 0.0,
    pathway_services: list[dict] | None = None,
) -> dict:
    """Simulate one family's annual cost on one plan given a utilization profile.

    utilization keys: primary_care_visits, specialist_visits, er_visits,
    generic_prescriptions, brand_prescriptions, planned_procedure_cost

    pathway_services, when supplied, are the *covered* portion of modeled
    clinical care (services beyond a visit cap or off formulary are excluded
    upstream and accounted for separately as an access gap).
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

    # Modeled clinical care from matched condition pathways. Billed through the
    # same cost-sharing rules, so pathway care competes for the same deductible
    # and out-of-pocket maximum as everything else.
    pathway_total = 0.0
    for service in pathway_services or []:
        quantity = int(round(service.get("annual_quantity", 0)))
        unit_cost = service.get("unit_cost", 0)
        if quantity <= 0 or unit_cost <= 0:
            continue

        service_type = service.get("service_type")
        copay_key = SERVICE_TYPE_COPAY_KEY.get(service_type)

        # Specialty-tier drugs are billed as coinsurance on the full price
        # rather than a flat copay — the whole point of the specialty tier.
        specialty_tier = service.get("specialty_tier", False)
        specialty_coinsurance = plan.get("specialty_rx_coinsurance")

        for _ in range(quantity):
            if specialty_tier and specialty_coinsurance is not None:
                paid, deductible_remaining, oop_remaining = _apply_deductible_coinsurance(
                    unit_cost, deductible_remaining, oop_remaining, specialty_coinsurance
                )
            elif uses_copays and copay_key and plan.get(copay_key) is not None:
                paid, oop_remaining = _apply_copay(plan[copay_key], oop_remaining)
            else:
                paid, deductible_remaining, oop_remaining = _apply_deductible_coinsurance(
                    unit_cost, deductible_remaining, oop_remaining, coinsurance
                )
            pathway_total += paid

    if pathway_total > 0:
        breakdown["condition_care_pathway"] = round(pathway_total, 2)

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


def build_recommendation(utilization: dict, pathway_services: list[dict] | None = None) -> list[dict]:
    plans = load_plans()
    results = []
    pathway_services = pathway_services or []

    best_case_utilization = {
        k: (v * BEST_CASE_UTILIZATION_FACTOR if k != "planned_procedure_cost" else v)
        for k, v in utilization.items()
    }

    for plan in plans:
        # Evaluate clinical access first: it determines which portion of the
        # pathway the plan actually covers, and what falls to the member.
        access = evaluate_plan_access(plan, pathway_services)
        billable = access["billable_services"]
        gap_cost = access["access_gap_cost"]

        expected = simulate_plan_cost(plan, utilization, pathway_services=billable)
        best_case = simulate_plan_cost(plan, best_case_utilization, pathway_services=billable)
        worst_case = simulate_plan_cost(
            plan, utilization, extra_shock=WORST_CASE_SHOCK, pathway_services=billable
        )

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
                # --- clinical access ---
                "access_score": access["access_score"],
                "access_findings": access["findings"],
                "access_gap_cost": gap_cost,
                "has_blocking_barrier": access["has_blocking_barrier"],
                # What the plan really costs once uncovered care is included.
                "access_adjusted_total_cost": round(expected["total_cost"] + gap_cost, 2),
            }
        )

    return results


# --- Access-vs-cost tradeoff policy -----------------------------------------
# These are explicit, tunable policy choices, not empirically derived values.
# They encode a judgment: for someone with an active chronic condition, a plan
# that cannot reliably deliver their care is not a bargain, and it is worth
# paying a bounded premium to avoid that. Employers may want these tuned, so
# they are named constants rather than buried magic numbers.
ACCESS_CONCERN_THRESHOLD = 60   # below this, access barriers are a real problem
MATERIAL_ACCESS_GAIN = 25       # points of improvement that count as "materially better"
MAX_PREMIUM_FOR_ACCESS = 0.20   # pay at most 20% more to escape a deficient plan


def pick_recommended_plan(results: list[dict]) -> str:
    """Rank on what care actually costs *and* whether it can be obtained.

    With no matched conditions this reduces to the original cost-only rule.
    With a care pathway in play, three things change:
      1. Uncovered care (beyond a visit cap, or off formulary) is added to cost.
      2. A plan that outright blocks a needed service is chosen only if every
         plan does.
      3. If the cheapest plan has poor clinical access, a materially better
         plan wins so long as it costs no more than MAX_PREMIUM_FOR_ACCESS more.
    """
    def sort_key(r: dict) -> float:
        return r.get("access_adjusted_total_cost", r["expected_total_cost"])

    # Prefer plans that can actually deliver the pathway, if any can.
    unblocked = [r for r in results if not r.get("has_blocking_barrier")]
    candidates = unblocked or results

    by_cost = sorted(candidates, key=sort_key)
    cheapest = by_cost[0]

    # Among near-equal-cost plans, prefer materially better downside protection.
    close_contenders = [r for r in by_cost if sort_key(r) <= sort_key(cheapest) * 1.05]
    best_protection = min(close_contenders, key=lambda r: r["worst_case_total_cost"])
    if best_protection["worst_case_total_cost"] < cheapest["worst_case_total_cost"] * 0.85:
        return best_protection["plan_id"]

    # If the cheapest plan can't reliably deliver this patient's care, look
    # further afield for one that can.
    if cheapest.get("access_score", 100) < ACCESS_CONCERN_THRESHOLD:
        affordable = [
            r for r in by_cost
            if sort_key(r) <= sort_key(cheapest) * (1 + MAX_PREMIUM_FOR_ACCESS)
        ]
        best_access = max(affordable, key=lambda r: r.get("access_score", 100))
        if best_access.get("access_score", 100) >= cheapest.get("access_score", 100) + MATERIAL_ACCESS_GAIN:
            return best_access["plan_id"]

    return cheapest["plan_id"]
