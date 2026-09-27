"""Medical practice builder & simulator.

The rest of PlanWise looks at health care from the patient's side of the
counter. This module looks from the other side: given a practice someone wants
to open (providers, staff, rooms, payer mix, overhead, financing), what does
its first few years look like month by month?

The model is deliberately mechanical and transparent, so every number on the
results page can be traced back to an input:

1. **Demand.** New patients arrive each month, ramping up linearly over
   `ramp_months` as the practice becomes known. Accepted patients join the
   active panel, which churns at `annual_attrition_pct` and returns
   `visits_per_patient_per_year` times a year.
2. **Capacity.** Bookable slots are the lesser of provider slots (count x clinic
   days x visits/day, from each provider's start month) and room slots (rooms x
   visits/room/day x open days). No-shows burn slots without producing a
   visit. Established patients are seen first; new patients are accepted only
   into what capacity is left, and the rest are turned away.
3. **Revenue.** Each completed visit bills `medicare_allowed_per_visit` scaled
   by each payer's rate. Claims are paid after that payer's `days_to_pay`;
   denied claims are partially recovered ~45 days later, and in-house recovery
   degrades when billing staff are overloaded. This lag is why a practice that
   is "profitable" on paper can still run out of cash.
4. **Costs & cash.** Payroll (with benefits load), rent, per-provider software
   and malpractice, per-visit supplies, marketing, other fixed costs, an
   outsourced billing fee if chosen, and amortized loan payments.

All template inputs are illustrative. See data/practice_templates.json.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from app.schemas import PracticeConfig

TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "data" / "practice_templates.json"

WEEKS_PER_MONTH = 52 / 12
DAYS_PER_MONTH = 365 / 12
# Extra time a denied claim takes to be appealed/resubmitted and paid.
DENIAL_REWORK_DAYS = 45
# Months averaged to describe the practice at "steady state" (end of horizon).
STEADY_STATE_MONTHS = 3


def load_templates() -> list[dict]:
    with open(TEMPLATES_PATH) as f:
        return json.load(f)["templates"]


def _add_lagged(schedule: list[float], month_index: int, lag_days: float, amount: float) -> None:
    """Book `amount` into `schedule` `lag_days` after the middle of a month.

    Visits happen throughout the month, so the payment is split linearly
    between the two months the lag straddles instead of landing in one lump.
    """
    offset = lag_days / DAYS_PER_MONTH
    whole = math.floor(offset)
    frac = offset - whole
    for idx, share in ((month_index + whole, 1 - frac), (month_index + whole + 1, frac)):
        if share > 0 and idx < len(schedule):
            schedule[idx] += amount * share


def _is_biller(role: str) -> bool:
    role = role.lower()
    return "bill" in role or "coder" in role or "revenue cycle" in role


def _monthly_loan_payment(principal: float, annual_rate_pct: float, term_months: int) -> float:
    if principal <= 0:
        return 0.0
    r = annual_rate_pct / 100 / 12
    if r == 0:
        return principal / term_months
    return principal * r / (1 - (1 + r) ** -term_months)


def _run(cfg: PracticeConfig) -> dict:
    n = cfg.months
    d = cfg.demand
    rev = cfg.revenue
    oh = cfg.overhead
    benefits = 1 + cfg.benefits_load_pct / 100
    no_show = d.no_show_pct / 100
    attrition_monthly = d.annual_attrition_pct / 100 / 12

    room_slots = cfg.exam_rooms * cfg.visits_per_room_per_day * cfg.open_days_per_week * WEEKS_PER_MONTH
    loan_payment = _monthly_loan_payment(
        cfg.startup.loan_amount, cfg.startup.loan_annual_rate_pct, cfg.startup.loan_term_months
    )
    starting_cash = (
        cfg.startup.owner_equity
        + cfg.startup.loan_amount
        - cfg.startup.buildout_and_equipment
        - cfg.startup.pre_opening_expenses
    )

    # Payment schedules run past the horizon only so the math stays simple;
    # anything landing after month n is simply not in the window.
    collections = [0.0] * n
    expected_collectible = [0.0] * n  # what each month's visits will eventually pay
    payer_totals = {
        p.payer: {"visits": 0.0, "collections": 0.0, "lost": 0.0} for p in cfg.payer_mix
    }

    panel = d.starting_panel
    months: list[dict] = []
    worst_billing_coverage = 1.0
    bottlenecks: list[str] = []

    for m in range(1, n + 1):
        i = m - 1
        # --- demand
        ramp = 1.0 if d.ramp_months <= 0 else min(1.0, m / d.ramp_months)
        arrivals = d.new_patients_per_month * ramp
        established_demand = panel * d.visits_per_patient_per_year / 12

        # --- capacity
        active = [p for p in cfg.providers if m >= p.start_month]
        provider_slots = sum(
            p.count * p.clinic_days_per_week * WEEKS_PER_MONTH * p.visits_per_day for p in active
        )
        slots = min(provider_slots, room_slots)
        effective_capacity = slots * (1 - no_show)

        established_seen = min(established_demand, effective_capacity)
        accepted = min(arrivals, max(0.0, effective_capacity - established_seen))
        turned_away = arrivals - accepted
        visits = established_seen + accepted
        booked = visits / (1 - no_show) if no_show < 1 else 0.0
        utilization = booked / slots * 100 if slots > 0 else 0.0

        constrained = turned_away > 0.5 or established_demand > effective_capacity + 0.5
        if not constrained:
            bottlenecks.append("demand")
        else:
            bottlenecks.append("rooms" if room_slots < provider_slots else "providers")

        panel = panel * (1 - attrition_monthly) + accepted

        # --- billing & collections
        if rev.billing_mode == "outsourced":
            coverage = 1.0
        else:
            billers = sum(s.count for s in cfg.staff if _is_biller(s.role) and m >= s.start_month)
            capacity_claims = billers * rev.claims_per_biller_per_month
            coverage = 1.0 if visits <= 0 else min(1.0, capacity_claims / visits)
        worst_billing_coverage = min(worst_billing_coverage, coverage)
        recovery = rev.denial_recovery_pct / 100 * coverage

        billed = 0.0
        for p in cfg.payer_mix:
            payer_visits = visits * p.share_pct / 100
            gross = payer_visits * rev.medicare_allowed_per_visit * p.rate_pct_of_medicare / 100
            denied = gross * p.denial_pct / 100
            first_pass = gross - denied
            recovered = denied * recovery
            billed += gross
            expected_collectible[i] += first_pass + recovered
            _add_lagged(collections, i, p.days_to_pay, first_pass)
            _add_lagged(collections, i, p.days_to_pay + DENIAL_REWORK_DAYS, recovered)
            t = payer_totals[p.payer]
            t["visits"] += payer_visits
            t["collections"] += first_pass + recovered
            t["lost"] += denied - recovered

        months.append(
            {
                "month": m,
                "active_patients": panel,
                "new_patients": accepted,
                "turned_away": turned_away,
                "capacity_visits": effective_capacity,
                "completed_visits": visits,
                "utilization_pct": utilization,
                "billed": billed,
                "_active_providers": sum(p.count for p in active),
                "_provider_payroll": sum(p.count * p.annual_salary for p in active) / 12 * benefits,
                "_staff_payroll": sum(
                    s.count * s.annual_salary for s in cfg.staff if m >= s.start_month
                ) / 12 * benefits,
            }
        )

    # --- expenses & cash, now that collections are fully scheduled
    cash = starting_cash
    cumulative_collectible = 0.0
    cumulative_collected = 0.0
    provider_payroll_by_month = []
    for i, row in enumerate(months):
        heads = row.pop("_active_providers")
        provider_payroll = row.pop("_provider_payroll")
        provider_payroll_by_month.append(provider_payroll)
        collected = collections[i]
        payroll = provider_payroll + row.pop("_staff_payroll")
        occupancy = oh.rent_per_month
        other = (
            heads * oh.software_per_provider_per_month
            + heads * oh.malpractice_per_provider_per_year / 12
            + row["completed_visits"] * oh.supplies_per_visit
            + oh.marketing_per_month
            + oh.other_fixed_per_month
        )
        if rev.billing_mode == "outsourced":
            other += collected * rev.outsourced_fee_pct / 100
        total = payroll + occupancy + other
        operating = collected - total
        debt = loan_payment if row["month"] <= cfg.startup.loan_term_months else 0.0
        net = operating - debt
        cash += net

        cumulative_collectible += expected_collectible[i]
        cumulative_collected += collected
        ar = max(0.0, cumulative_collectible - cumulative_collected)
        recent = months[max(0, i - 2) : i + 1]
        daily_billed = sum(r["billed"] for r in recent) / len(recent) / DAYS_PER_MONTH
        row.update(
            collections=collected,
            payroll=payroll,
            occupancy=occupancy,
            other_expenses=other,
            total_expenses=total,
            operating_income=operating,
            debt_service=debt,
            net_cash_flow=net,
            cash_balance=cash,
            accounts_receivable=ar,
            days_in_ar=ar / daily_billed if daily_billed > 0 else 0.0,
        )

    return {
        "months": months,
        "starting_cash": starting_cash,
        "payer_totals": payer_totals,
        "worst_billing_coverage": worst_billing_coverage,
        "bottlenecks": bottlenecks,
        "billers": sum(s.count for s in cfg.staff if _is_biller(s.role)),
        "provider_payroll": provider_payroll_by_month,
    }


def _summarize(cfg: PracticeConfig, run: dict) -> dict:
    months = run["months"]
    n = len(months)

    breakeven = None
    for idx in range(n - 1, -1, -1):
        if months[idx]["operating_income"] < 0:
            break
        breakeven = months[idx]["month"]

    # Cash payback: the month cumulative net cash flow since opening climbs back
    # to zero, i.e. operations have repaid every dollar they burned while ramping.
    payback, cumulative, dipped = None, 0.0, False
    for r in months:
        cumulative += r["net_cash_flow"]
        if cumulative < 0:
            dipped = True
        elif dipped or r["month"] == 1:
            payback = r["month"]
            break

    lowest_cash, lowest_month = run["starting_cash"], 0
    for r in months:
        if r["cash_balance"] < lowest_cash:
            lowest_cash, lowest_month = r["cash_balance"], r["month"]

    tail = months[-STEADY_STATE_MONTHS:]
    ss_visits = sum(r["completed_visits"] for r in tail) / len(tail)
    ss_util = sum(r["utilization_pct"] for r in tail) / len(tail)
    ss_collections = sum(r["collections"] for r in tail) / len(tail)
    ss_operating = sum(r["operating_income"] for r in tail) / len(tail)

    last_year = months[-12:]
    ly_collections = sum(r["collections"] for r in last_year)
    ly_visits = sum(r["completed_visits"] for r in last_year)
    # Overhead ratio = everything except provider compensation, the usual MGMA framing.
    ly_overhead = sum(r["total_expenses"] for r in last_year) - sum(run["provider_payroll"][-12:])

    recent = run["bottlenecks"][-STEADY_STATE_MONTHS:]
    bottleneck = max(set(recent), key=recent.count)

    return {
        "starting_cash": run["starting_cash"],
        "operating_breakeven_month": breakeven,
        "cash_payback_month": payback,
        "lowest_cash": lowest_cash,
        "lowest_cash_month": lowest_month,
        "ending_cash": months[-1]["cash_balance"],
        "steady_state_visits_per_month": ss_visits,
        "steady_state_utilization_pct": ss_util,
        "steady_state_collections_per_month": ss_collections,
        "steady_state_operating_margin_pct": (
            ss_operating / ss_collections * 100 if ss_collections > 0 else 0.0
        ),
        "net_collection_per_visit": ly_collections / ly_visits if ly_visits > 0 else 0.0,
        "overhead_ratio_pct": ly_overhead / ly_collections * 100 if ly_collections > 0 else 0.0,
        "bottleneck": bottleneck,
        "final_year_operating_income": sum(r["operating_income"] for r in last_year),
    }


def _years(months: list[dict]) -> list[dict]:
    out = []
    for start in range(0, len(months), 12):
        chunk = months[start : start + 12]
        collections = sum(r["collections"] for r in chunk)
        operating = sum(r["operating_income"] for r in chunk)
        out.append(
            {
                "year": start // 12 + 1,
                "visits": sum(r["completed_visits"] for r in chunk),
                "collections": collections,
                "expenses": sum(r["total_expenses"] for r in chunk),
                "operating_income": operating,
                "net_cash_flow": sum(r["net_cash_flow"] for r in chunk),
                "operating_margin_pct": operating / collections * 100 if collections > 0 else 0.0,
            }
        )
    return out


def _payers(cfg: PracticeConfig, run: dict) -> list[dict]:
    rev = cfg.revenue
    out = []
    for p in cfg.payer_mix:
        t = run["payer_totals"][p.payer]
        out.append(
            {
                "payer": p.payer,
                "share_pct": p.share_pct,
                "net_per_visit": t["collections"] / t["visits"] if t["visits"] > 0 else (
                    rev.medicare_allowed_per_visit * p.rate_pct_of_medicare / 100
                    * (1 - p.denial_pct / 100)
                ),
                "visits": t["visits"],
                "collections": t["collections"],
                "lost_to_denials": t["lost"],
            }
        )
    return out


def _money(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.0f}"


def _insights(cfg: PracticeConfig, run: dict, summary: dict, payers: list[dict]) -> list[dict]:
    months = run["months"]
    tail = months[-STEADY_STATE_MONTHS:]
    out: list[dict] = []

    if summary["lowest_cash"] < 0:
        first_negative = next(r["month"] for r in months if r["cash_balance"] < 0)
        out.append(
            {
                "severity": "blocking",
                "title": f"Runs out of cash in month {first_negative}",
                "detail": (
                    f"Cash bottoms out at {_money(summary['lowest_cash'])} in month "
                    f"{summary['lowest_cash_month']}. You need at least "
                    f"{_money(-summary['lowest_cash'])} more in equity, loan or a line of credit "
                    "(plus a cushion) before opening. Collections lag visits by weeks, so the "
                    "cash trough comes after the practice is already busy."
                ),
            }
        )
    if summary["operating_breakeven_month"] is None:
        out.append(
            {
                "severity": "blocking",
                "title": "Never reaches sustained operating break-even",
                "detail": (
                    f"Operating income over the final year is {_money(summary['final_year_operating_income'])}. "
                    "Costs exceed collections even at steady state; see the bottleneck and sensitivity "
                    "sections for which lever moves it most."
                ),
            }
        )
    elif summary["operating_breakeven_month"] > 18:
        out.append(
            {
                "severity": "medium",
                "title": f"Slow path to break-even (month {summary['operating_breakeven_month']})",
                "detail": "Most lenders and owners plan for 12-18 months. A slower ramp means a deeper cash reserve.",
            }
        )

    turned_away = sum(r["turned_away"] for r in tail) / len(tail)
    if summary["bottleneck"] != "demand":
        what = (
            "exam rooms" if summary["bottleneck"] == "rooms" else "provider time"
        )
        fix = (
            "Add exam rooms or extend hours — providers have unused slots the rooms can't hold."
            if summary["bottleneck"] == "rooms"
            else "Adding a provider (or clinic days) is the direct lever; rooms still have slack."
        )
        net_visit = summary["net_collection_per_visit"]
        out.append(
            {
                "severity": "high",
                "title": f"Capacity-constrained by {what}",
                "detail": (
                    f"About {turned_away:,.0f} new patients a month are turned away at steady state "
                    f"(each worth ~{cfg.demand.visits_per_patient_per_year:.1f} visits/year at ~{_money(net_visit)} per visit). {fix}"
                ),
            }
        )
    elif summary["steady_state_utilization_pct"] < 65:
        out.append(
            {
                "severity": "medium",
                "title": f"Schedule only {summary['steady_state_utilization_pct']:.0f}% full at steady state",
                "detail": (
                    "Demand doesn't fill the capacity you're paying for. Consider delaying a hire "
                    "(later start month), fewer clinic days, or more marketing/referral development."
                ),
            }
        )

    if cfg.revenue.billing_mode == "in_house" and run["worst_billing_coverage"] < 0.999:
        pct = run["worst_billing_coverage"] * 100
        out.append(
            {
                "severity": "high" if pct < 70 else "medium",
                "title": "Billing staff can't keep up with claim volume",
                "detail": (
                    f"{run['billers']} biller(s) cover only {pct:.0f}% of peak claim volume, so denied "
                    "claims go unworked and are written off. Add billing staff (roles containing "
                    "\"bill\" or \"coder\" count) or switch to outsourced billing."
                ),
            }
        )

    total_collect = sum(p["collections"] for p in payers)
    total_lost = sum(p["lost_to_denials"] for p in payers)
    if total_collect > 0 and total_lost / (total_collect + total_lost) > 0.05:
        worst = max(payers, key=lambda p: p["lost_to_denials"])
        out.append(
            {
                "severity": "medium",
                "title": f"{_money(total_lost)} written off to unrecovered denials",
                "detail": (
                    f"{total_lost / (total_collect + total_lost) * 100:.1f}% of expected revenue is lost; "
                    f"{worst['payer']} is the largest source. Front-desk eligibility checks and prior "
                    "auth tracking are the usual fixes."
                ),
            }
        )

    weighted_rate = sum(p.share_pct * p.rate_pct_of_medicare for p in cfg.payer_mix) / 100
    if weighted_rate < 105:
        out.append(
            {
                "severity": "medium",
                "title": f"Payer mix pays {weighted_rate:.0f}% of Medicare on average",
                "detail": (
                    "Low-rate payers dominate. Volume has to carry the practice; negotiate commercial "
                    "contracts before opening, or cap low-rate panel share."
                ),
            }
        )

    if cfg.demand.no_show_pct >= 10:
        ns = cfg.demand.no_show_pct / 100
        lost_visits = sum(r["completed_visits"] for r in tail) / len(tail) / (1 - ns) * ns
        out.append(
            {
                "severity": "medium" if summary["bottleneck"] != "demand" else "low",
                "title": f"{cfg.demand.no_show_pct:.0f}% no-show rate",
                "detail": (
                    f"~{lost_visits:,.0f} booked slots a month go empty. Reminders and strategic "
                    "overbooking recover much of this — it matters most when you're capacity-constrained."
                ),
            }
        )

    ar_days = months[-1]["days_in_ar"]
    if ar_days > 50:
        out.append(
            {
                "severity": "medium",
                "title": f"{ar_days:.0f} days in A/R",
                "detail": "Slow-paying payers tie up working capital. Healthy outpatient practices run 30-45 days.",
            }
        )

    if summary["overhead_ratio_pct"] > 65:
        out.append(
            {
                "severity": "medium",
                "title": f"Overhead is {summary['overhead_ratio_pct']:.0f}% of collections",
                "detail": "Non-provider costs leave little for provider compensation and profit (often 55-60% in efficient practices).",
            }
        )

    late = [p for p in cfg.providers if p.start_month > cfg.months]
    if late:
        out.append(
            {
                "severity": "low",
                "title": "A provider starts after the simulation ends",
                "detail": ", ".join(p.role for p in late) + " never appear in this horizon.",
            }
        )

    if not any(i["severity"] in ("blocking", "high") for i in out) and summary["steady_state_operating_margin_pct"] >= 15:
        out.append(
            {
                "severity": "good",
                "title": f"Healthy {summary['steady_state_operating_margin_pct']:.0f}% operating margin at steady state",
                "detail": "Collections comfortably cover costs and debt service once the panel matures.",
            }
        )

    order = {"blocking": 0, "high": 1, "medium": 2, "low": 3, "good": 4}
    return sorted(out, key=lambda x: order[x["severity"]])


def _final_year_income(cfg: PracticeConfig) -> float:
    return sum(r["operating_income"] for r in _run(cfg)["months"][-12:])


def _sensitivity(cfg: PracticeConfig) -> list[dict]:
    """One-at-a-time swings on the drivers owners most often get wrong."""

    def scaled(mutate) -> float:
        c = cfg.model_copy(deep=True)
        mutate(c)
        return _final_year_income(c)

    def salaries(c: PracticeConfig, f: float) -> None:
        for p in c.providers:
            p.annual_salary *= f
        for s in c.staff:
            s.annual_salary *= f

    def productivity(c: PracticeConfig, f: float) -> None:
        for p in c.providers:
            p.visits_per_day *= f

    ns = cfg.demand.no_show_pct
    drivers = [
        ("Reimbursement per visit", "-10%", "+10%",
         lambda c, f: setattr(c.revenue, "medicare_allowed_per_visit", c.revenue.medicare_allowed_per_visit * f), 0.9, 1.1),
        ("New-patient demand", "-25%", "+25%",
         lambda c, f: setattr(c.demand, "new_patients_per_month", c.demand.new_patients_per_month * f), 0.75, 1.25),
        ("Provider visits per day", "-10%", "+10%", productivity, 0.9, 1.1),
        ("Salaries", "+10%", "-10%", salaries, 1.1, 0.9),
        ("Rent", "+25%", "-25%",
         lambda c, f: setattr(c.overhead, "rent_per_month", c.overhead.rent_per_month * f), 1.25, 0.75),
        (
            "No-show rate",
            f"{min(90, ns + 5):.0f}%",
            f"{max(0, ns - 5):.0f}%",
            lambda c, v: setattr(c.demand, "no_show_pct", v),
            min(90.0, ns + 5),
            max(0.0, ns - 5),
        ),
    ]
    rows = []
    for name, low_label, high_label, mutate, low_arg, high_arg in drivers:
        rows.append(
            {
                "driver": name,
                "low_label": low_label,
                "high_label": high_label,
                "low_value": scaled(lambda c, m=mutate, a=low_arg: m(c, a)),
                "high_value": scaled(lambda c, m=mutate, a=high_arg: m(c, a)),
            }
        )
    rows.sort(key=lambda r: abs(r["high_value"] - r["low_value"]), reverse=True)
    return rows


def simulate(cfg: PracticeConfig) -> dict:
    run = _run(cfg)
    summary = _summarize(cfg, run)
    payers = _payers(cfg, run)
    return {
        "summary": summary,
        "months": run["months"],
        "years": _years(run["months"]),
        "payers": payers,
        "insights": _insights(cfg, run, summary, payers),
        "sensitivity": _sensitivity(cfg),
    }
