from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Expense, FamilyMember, MedicalCondition, User
from app.schemas import PlanCost, RecommendationResponse
from app.services.llm import generate_explanation
from app.services.recommendation import build_recommendation, pick_recommended_plan

router = APIRouter(prefix="/recommend", tags=["recommend"])


def _aggregate_utilization(db: Session, user: User) -> dict:
    members = db.query(FamilyMember).filter(FamilyMember.user_id == user.id).all()
    totals = {
        "primary_care_visits": 0,
        "specialist_visits": 0,
        "er_visits": 0,
        "generic_prescriptions": 0,
        "brand_prescriptions": 0,
        "planned_procedure_cost": 0.0,
    }
    for m in members:
        totals["primary_care_visits"] += m.expected_primary_care_visits or 0
        totals["specialist_visits"] += m.expected_specialist_visits or 0
        totals["er_visits"] += m.expected_er_visits or 0
        totals["generic_prescriptions"] += m.expected_generic_prescriptions or 0
        totals["brand_prescriptions"] += m.expected_brand_prescriptions or 0
        totals["planned_procedure_cost"] += m.planned_procedure_cost or 0
    return totals, members


@router.get("", response_model=RecommendationResponse)
def get_recommendation(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    utilization, members = _aggregate_utilization(db, user)
    results = build_recommendation(utilization)
    recommended_plan_id = pick_recommended_plan(results)

    lowest_expected = min(results, key=lambda r: r["expected_total_cost"])["plan_id"]
    best_worst_case = min(results, key=lambda r: r["worst_case_total_cost"])["plan_id"]

    expenses = db.query(Expense).filter(Expense.user_id == user.id).all()
    expense_totals: dict[str, float] = {}
    for e in expenses:
        expense_totals[e.category] = expense_totals.get(e.category, 0) + e.amount

    family_context = {
        "family_size": len(members),
        "members": [
            {
                "relation": m.relation,
                "age": m.age,
                "conditions": [c.name for c in m.conditions],
                "ongoing_medications": len(m.medications),
            }
            for m in members
        ],
        "expected_annual_utilization": utilization,
        "historical_expenses_by_category": expense_totals,
    }

    explanation = generate_explanation(results, recommended_plan_id, family_context)

    return RecommendationResponse(
        plans=[PlanCost(**r) for r in results],
        recommended_plan_id=recommended_plan_id,
        lowest_expected_cost_plan_id=lowest_expected,
        best_worst_case_plan_id=best_worst_case,
        explanation=explanation,
    )
