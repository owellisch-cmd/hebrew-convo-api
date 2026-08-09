"""Turns the rule-based recommendation numbers into a plain-English
explanation using Claude. Falls back to a deterministic templated summary if
no API key is configured, so the app still works without one.
"""

from __future__ import annotations

import json

import anthropic

from app.config import settings

MODEL = "claude-opus-5"


def _fallback_explanation(results: list[dict], recommended_plan_id: str) -> str:
    recommended = next(r for r in results if r["plan_id"] == recommended_plan_id)
    cheapest = min(results, key=lambda r: r["expected_total_cost"])

    def true_cost(plan: dict) -> float:
        return plan.get("access_adjusted_total_cost") or plan["expected_total_cost"]

    lines = [
        f"Based on your family's expected usage, {recommended['plan_name']} has an estimated "
        f"total annual cost of ${true_cost(recommended):,.0f} "
        f"(${recommended['annual_premium']:,.0f} in premiums plus "
        f"${recommended['expected_out_of_pocket']:,.0f} in expected out-of-pocket costs"
        + (
            f", plus ${recommended['access_gap_cost']:,.0f} of care this plan does not cover"
            if recommended.get("access_gap_cost")
            else ""
        )
        + ").",
    ]

    if recommended["plan_id"] != cheapest["plan_id"]:
        # Explain the *actual* reason this plan beat the cheaper one, rather than
        # assuming it is always downside protection.
        gap = cheapest.get("access_gap_cost", 0)
        if gap > 0 or cheapest.get("has_blocking_barrier"):
            lines.append(
                f"{cheapest['plan_name']} looks cheaper at first "
                f"(${cheapest['expected_total_cost']:,.0f}), but it does not cover roughly "
                f"${gap:,.0f} of the care your condition requires. You would pay that in full, "
                f"and it would not count toward your out-of-pocket maximum, bringing its real "
                f"cost to ${true_cost(cheapest):,.0f}."
            )
            if cheapest.get("access_score", 100) < recommended.get("access_score", 100):
                lines.append(
                    f"It also scores {cheapest['access_score']}/100 on delivering that care, "
                    f"versus {recommended['access_score']}/100 for {recommended['plan_name']}."
                )
            # Be explicit when the recommendation is a deliberate trade of money
            # for reliable access, rather than letting it read as the cheaper option.
            if true_cost(recommended) > true_cost(cheapest):
                lines.append(
                    f"{recommended['plan_name']} does cost about "
                    f"${true_cost(recommended) - true_cost(cheapest):,.0f} more per year. That "
                    f"is the trade being recommended: paying more to get care you can actually "
                    f"use, rather than paying less for coverage that stops short of what your "
                    f"condition needs."
                )
        elif cheapest["worst_case_total_cost"] > recommended["worst_case_total_cost"]:
            lines.append(
                f"{cheapest['plan_name']} has a lower expected cost "
                f"(${cheapest['expected_total_cost']:,.0f}), but in a bad year it could cost "
                f"${cheapest['worst_case_total_cost']:,.0f} versus "
                f"${recommended['worst_case_total_cost']:,.0f} for {recommended['plan_name']}, "
                "so it offers less protection if something unexpected happens."
            )
        else:
            lines.append(
                f"{cheapest['plan_name']} has a lower expected cost "
                f"(${cheapest['expected_total_cost']:,.0f}), but "
                f"{recommended['plan_name']} scores better on delivering the care your "
                f"condition requires ({recommended.get('access_score', 100)}/100 versus "
                f"{cheapest.get('access_score', 100)}/100)."
            )

    lines.append(
        "This is an automated estimate using national average costs, not a guarantee — "
        "confirm exact numbers with your benefits team before enrolling."
    )
    return " ".join(lines)


def generate_explanation(
    results: list[dict],
    recommended_plan_id: str,
    family_context: dict,
) -> str:
    if not settings.anthropic_api_key:
        return _fallback_explanation(results, recommended_plan_id)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    prompt = f"""You are helping an employee choose a health insurance plan for their family.

Family context (self-reported, for your context only — do not repeat verbatim, this may include sensitive medical details):
{json.dumps(family_context, indent=2)}

Plan cost simulation results (computed by a rule-based cost engine — these numbers are ground truth, do not recompute or alter them):
{json.dumps(results, indent=2)}

The recommended plan (chosen by the engine) is: {recommended_plan_id}

Each plan also carries clinical-access data, which matters as much as price:
- "access_score" (0-100): how well the plan delivers the care this family's conditions require.
- "access_findings": specific barriers (visit caps, prior authorization, step therapy, thin
  specialist networks, drugs off formulary).
- "access_gap_cost": care the plan does NOT cover, paid entirely by the member. Critically, this
  spending does not count toward the deductible or out-of-pocket maximum.
- "access_adjusted_total_cost": the plan's true cost once uncovered care is included.

Write a short, plain-English explanation (150-250 words) of why this plan is the recommended
choice for this family, referencing the actual dollar figures above.

Important: if a cheaper-looking plan was passed over, explain the real reason using the data —
usually either uncovered care (access_gap_cost) or a specific coverage barrier, not just
worst-case risk. Be concrete about the barrier (for example, a visit cap short of what the
pathway needs, or a drug that is not on the formulary). Never state a comparison the numbers do
not support.

Do not invent numbers not present in the data. Do not give medical advice or suggest treatment —
describe coverage and cost only. End with a one-sentence reminder that this is an estimate and
they should confirm details with their benefits team. Write directly to the employee ("you",
"your family")."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": prompt}],
    )

    if response.stop_reason == "refusal":
        return _fallback_explanation(results, recommended_plan_id)

    text_blocks = [block.text for block in response.content if block.type == "text"]
    text = "\n".join(text_blocks).strip()
    return text or _fallback_explanation(results, recommended_plan_id)
