"""Clinical care-pathway modeling.

The rest of the engine answers "what will this plan cost?". This module answers
a different question: "can I actually get the care my condition requires under
this plan?"

A condition maps to a *care pathway* — a modeled year of the services someone
with that condition typically needs. Each service carries access requirements
(visit caps, prior authorization, step therapy, in-network specialty
availability, formulary placement). Each plan is then evaluated against that
pathway to surface concrete barriers, not just dollars.

The key modeling insight: services beyond a visit cap, or drugs off formulary,
are **not covered at all**. The member pays full price and — unlike normal cost
sharing — that spending does *not* count toward the deductible or out-of-pocket
maximum. That is precisely how a low-premium plan can end up costing more for a
patient with a chronic condition, which a premium-plus-copay model cannot see.

All quantities and unit costs are illustrative planning estimates, not clinical
guidance. See the disclaimer in data/care_pathways.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PATHWAYS_PATH = Path(__file__).resolve().parent.parent / "data" / "care_pathways.json"

# Severity -> points deducted from a 100-point access score.
SEVERITY_WEIGHTS = {
    "blocking": 34,
    "high": 18,
    "medium": 8,
    "low": 3,
}

# Formulary tier -> how the drug is billed.
SPECIALTY_TIERS = {"specialty"}


def load_pathways() -> list[dict]:
    with open(PATHWAYS_PATH) as f:
        return json.load(f)["pathways"]


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()).strip()


def match_pathway(condition_name: str) -> dict | None:
    """Map a free-text condition to a known pathway.

    Matching is alias-based rather than requiring a foreign key, so conditions
    users already typed as free text keep working with no migration.
    """
    normalized = _normalize(condition_name)
    if not normalized:
        return None

    for pathway in load_pathways():
        for alias in pathway["aliases"]:
            alias_norm = _normalize(alias)
            # Exact match, or the alias appears as a whole phrase in the input.
            if normalized == alias_norm or re.search(rf"\b{re.escape(alias_norm)}\b", normalized):
                return pathway
    return None


def match_pathways(condition_names: list[str]) -> list[dict]:
    """Match a list of conditions to distinct pathways (deduplicated)."""
    matched: dict[str, dict] = {}
    for name in condition_names:
        pathway = match_pathway(name)
        if pathway and pathway["id"] not in matched:
            matched[pathway["id"]] = {**pathway, "matched_from": name}
    return list(matched.values())


def collect_services(pathways: list[dict]) -> list[dict]:
    """Flatten matched pathways into a single list of projected services."""
    services: list[dict] = []
    for pathway in pathways:
        for service in pathway["services"]:
            services.append({**service, "pathway_id": pathway["id"], "pathway_name": pathway["name"]})
    return services


def _finding(severity: str, kind: str, service: dict, message: str, uncovered_cost: float = 0.0) -> dict:
    return {
        "severity": severity,
        "type": kind,
        "service_name": service["name"],
        "pathway_name": service.get("pathway_name", ""),
        "message": message,
        "uncovered_cost": round(uncovered_cost, 2),
    }


def evaluate_plan_access(plan: dict, services: list[dict]) -> dict:
    """Evaluate one plan against a set of projected pathway services.

    Returns the access score, the concrete barriers found, the portion of care
    the plan actually covers (to be billed through normal cost sharing), and
    the out-of-pocket cost of the portion it does not cover.
    """
    access = plan.get("access") or {}
    visit_caps = access.get("visit_caps", {})
    prior_auth = set(access.get("prior_auth", []))
    step_therapy = set(access.get("step_therapy", []))
    specialty_network = access.get("specialty_network", {})
    formulary = access.get("formulary", {})

    findings: list[dict] = []
    billable: list[dict] = []
    gap_cost = 0.0

    # Track cap consumption across services that share a cap category, so two
    # pathways both needing physical therapy correctly compete for one cap.
    cap_used: dict[str, int] = {}

    for service in services:
        requires = service.get("requires", {})
        quantity = service.get("annual_quantity", 0)
        unit_cost = service.get("unit_cost", 0)
        covered_quantity = quantity

        # --- Visit caps: care beyond the cap is simply not covered -----------
        cap_category = requires.get("visit_cap_category")
        if cap_category:
            cap = visit_caps.get(cap_category)
            if cap is None:
                covered_quantity = 0
                uncovered_cost = quantity * unit_cost
                gap_cost += uncovered_cost
                findings.append(
                    _finding(
                        "blocking",
                        "benefit_not_covered",
                        service,
                        f"{service['name']} is not a covered benefit under this plan. "
                        f"All {quantity} projected visits would be paid entirely out of pocket "
                        f"(about ${uncovered_cost:,.0f}), and none of it counts toward your deductible "
                        f"or out-of-pocket maximum.",
                        uncovered_cost,
                    )
                )
            else:
                already_used = cap_used.get(cap_category, 0)
                remaining = max(cap - already_used, 0)
                covered_quantity = min(quantity, remaining)
                cap_used[cap_category] = already_used + covered_quantity
                shortfall = quantity - covered_quantity
                if shortfall > 0:
                    uncovered_cost = shortfall * unit_cost
                    gap_cost += uncovered_cost
                    findings.append(
                        _finding(
                            "high",
                            "visit_cap_shortfall",
                            service,
                            f"This plan covers {cap} {cap_category.replace('_', ' ')} visits per year, "
                            f"but your care pathway projects {quantity}. The remaining {shortfall} visits "
                            f"(about ${uncovered_cost:,.0f}) would be paid entirely out of pocket and would "
                            f"not count toward your out-of-pocket maximum.",
                            uncovered_cost,
                        )
                    )

        # --- Formulary placement --------------------------------------------
        drug_class = requires.get("formulary_class")
        if drug_class:
            entry = formulary.get(drug_class)
            if entry is None or not entry.get("covered", False):
                covered_quantity = 0
                uncovered_cost = quantity * unit_cost
                gap_cost += uncovered_cost
                findings.append(
                    _finding(
                        "blocking",
                        "drug_not_covered",
                        service,
                        f"{service['name']} is not on this plan's formulary. You would pay the full "
                        f"cost (about ${uncovered_cost:,.0f}/year), with none of it counting toward your "
                        f"out-of-pocket maximum, or need to switch therapy.",
                        uncovered_cost,
                    )
                )
            elif entry.get("tier") in SPECIALTY_TIERS:
                service = {**service, "specialty_tier": True}
                findings.append(
                    _finding(
                        "medium",
                        "specialty_tier",
                        service,
                        f"{service['name']} sits on the specialty tier, billed as coinsurance rather than "
                        f"a flat copay — your share scales with the drug's full price.",
                    )
                )

        # --- In-network availability of the required specialty ---------------
        specialty = requires.get("specialty_network")
        if specialty:
            adequacy = specialty_network.get(specialty, "none")
            if adequacy == "none":
                if not plan.get("out_of_network_coverage"):
                    covered_quantity = 0
                    uncovered_cost = quantity * unit_cost
                    gap_cost += uncovered_cost
                    findings.append(
                        _finding(
                            "blocking",
                            "no_in_network_specialist",
                            service,
                            f"This plan has no in-network {specialty.replace('_', ' ')} providers and does "
                            f"not cover out-of-network care. You would pay the full cost of these visits "
                            f"(about ${uncovered_cost:,.0f}).",
                            uncovered_cost,
                        )
                    )
                else:
                    findings.append(
                        _finding(
                            "high",
                            "out_of_network_specialist",
                            service,
                            f"No in-network {specialty.replace('_', ' ')} providers. You can still go "
                            f"out of network, but at a higher cost share.",
                        )
                    )
            elif adequacy == "limited":
                findings.append(
                    _finding(
                        "high",
                        "limited_specialist_network",
                        service,
                        f"This plan's {specialty.replace('_', ' ')} network is limited — expect longer waits "
                        f"and possibly significant travel to be seen. For an active condition, delay in "
                        f"getting care is itself a cost.",
                    )
                )

        # --- Prior authorization and step therapy ---------------------------
        pa_category = requires.get("prior_auth_category")
        if pa_category and pa_category in prior_auth:
            findings.append(
                _finding(
                    "medium",
                    "prior_authorization",
                    service,
                    f"{service['name']} requires prior authorization. Expect a submission-and-approval "
                    f"delay before the service can be scheduled, and a real chance of initial denial.",
                )
            )

        st_category = requires.get("step_therapy_category")
        if st_category and st_category in step_therapy:
            findings.append(
                _finding(
                    "high",
                    "step_therapy",
                    service,
                    f"{service['name']} is gated behind step therapy — you must document failure of "
                    f"lower-cost treatment first. Combined with a visit cap on physical therapy, this can "
                    f"create a catch-22: you cannot complete the conservative therapy the plan requires "
                    f"before it will approve the next step.",
                )
            )

        if requires.get("referral") and plan.get("requires_referral"):
            findings.append(
                _finding(
                    "low",
                    "referral_required",
                    service,
                    f"Seeing this specialist requires a referral from your primary care doctor first, "
                    f"adding a visit and a scheduling delay.",
                )
            )

        if covered_quantity > 0:
            billable.append({**service, "annual_quantity": covered_quantity})

    score = 100
    for finding in findings:
        score -= SEVERITY_WEIGHTS.get(finding["severity"], 0)
    score = max(score, 0)

    severity_rank = {"blocking": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: severity_rank.get(f["severity"], 9))

    return {
        "access_score": score,
        "findings": findings,
        "billable_services": billable,
        "access_gap_cost": round(gap_cost, 2),
        "has_blocking_barrier": any(f["severity"] == "blocking" for f in findings),
    }
