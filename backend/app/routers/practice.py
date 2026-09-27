from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Practice, User
from app.schemas import (
    PracticeConfig,
    PracticeIn,
    PracticeOut,
    PracticeTemplate,
    SimulationResult,
)
from app.services.practice_sim import load_templates, simulate

router = APIRouter(prefix="/practice", tags=["practice"])


def _get_practice(db: Session, user: User, practice_id: int) -> Practice:
    practice = (
        db.query(Practice)
        .filter(Practice.id == practice_id, Practice.user_id == user.id)
        .first()
    )
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")
    return practice


@router.get("/templates", response_model=list[PracticeTemplate])
def list_templates():
    """Starting points per specialty. Every number is meant to be edited."""
    return load_templates()


@router.post("/simulate", response_model=SimulationResult)
def run_simulation(config: PracticeConfig, user: User = Depends(get_current_user)):
    """Simulate an unsaved design, so the builder can iterate without saving."""
    return simulate(config)


@router.get("/saved", response_model=list[PracticeOut])
def list_practices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Practice)
        .filter(Practice.user_id == user.id)
        .order_by(Practice.updated_at.desc())
        .all()
    )


@router.post("/saved", response_model=PracticeOut, status_code=201)
def create_practice(
    payload: PracticeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    practice = Practice(user_id=user.id, name=payload.name, config=payload.config.model_dump())
    db.add(practice)
    db.commit()
    db.refresh(practice)
    return practice


@router.put("/saved/{practice_id}", response_model=PracticeOut)
def update_practice(
    practice_id: int,
    payload: PracticeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    practice = _get_practice(db, user, practice_id)
    practice.name = payload.name
    practice.config = payload.config.model_dump()
    db.commit()
    db.refresh(practice)
    return practice


@router.delete("/saved/{practice_id}", status_code=204)
def delete_practice(
    practice_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    db.delete(_get_practice(db, user, practice_id))
    db.commit()
