from fastapi import APIRouter

from app.services.recommendation import load_plans

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("")
def list_plans():
    return load_plans()
