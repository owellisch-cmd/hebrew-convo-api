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
    lines = [
        f"Based on your family's expected usage, {recommended['plan_name']} has an estimated "
        f"total annual cost of ${recommended['expected_total_cost']:,.0f} "
        f"(${recommended['annual_premium']:,.0f} in premiums plus "
        f"${recommended['expected_out_of_pocket']:,.0f} in expected out-of-pocket costs).",
    ]
    if recommended["plan_id"] != cheapest["plan_id"]:
        lines.append(
            f"{cheapest['plan_name']} has a slightly lower expected cost "
            f"(${cheapest['expected_total_cost']:,.0f}), but in a bad year its worst-case cost "
            f"(${cheapest['worst_case_total_cost']:,.0f}) is meaningfully higher than "
            f"{recommended['plan_name']}'s (${recommended['worst_case_total_cost']:,.0f}), "
            "so it offers less protection if something unexpected happens."
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

The recommended plan (chosen by the cost engine) is: {recommended_plan_id}

Write a short, plain-English explanation (150-250 words) of why this plan is the recommended
choice for this family, referencing the actual dollar figures above. If another plan is close in
expected cost but offers meaningfully better protection against a bad year (or vice versa), mention
that tradeoff. Do not invent numbers not present in the data. Do not give specific medical advice.
End with a one-sentence reminder that this is an estimate and they should confirm details with their
benefits team. Write directly to the employee ("you", "your family")."""

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
