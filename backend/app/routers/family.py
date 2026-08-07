from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import FamilyMember, MedicalCondition, Medication, User
from app.schemas import (
    ConditionIn,
    ConditionOut,
    FamilyMemberIn,
    FamilyMemberOut,
    MedicationIn,
    MedicationOut,
)

router = APIRouter(prefix="/family", tags=["family"])


def _get_member(db: Session, user: User, member_id: int) -> FamilyMember:
    member = (
        db.query(FamilyMember)
        .filter(FamilyMember.id == member_id, FamilyMember.user_id == user.id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Family member not found")
    return member


@router.get("", response_model=list[FamilyMemberOut])
def list_family(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(FamilyMember).filter(FamilyMember.user_id == user.id).all()


@router.post("", response_model=FamilyMemberOut, status_code=201)
def create_family_member(
    payload: FamilyMemberIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = FamilyMember(user_id=user.id, **payload.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.put("/{member_id}", response_model=FamilyMemberOut)
def update_family_member(
    member_id: int,
    payload: FamilyMemberIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _get_member(db, user, member_id)
    for key, value in payload.model_dump().items():
        setattr(member, key, value)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}", status_code=204)
def delete_family_member(
    member_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _get_member(db, user, member_id)
    db.delete(member)
    db.commit()


@router.post("/{member_id}/conditions", response_model=ConditionOut, status_code=201)
def add_condition(
    member_id: int,
    payload: ConditionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _get_member(db, user, member_id)
    condition = MedicalCondition(family_member_id=member.id, **payload.model_dump())
    db.add(condition)
    db.commit()
    db.refresh(condition)
    return condition


@router.delete("/{member_id}/conditions/{condition_id}", status_code=204)
def delete_condition(
    member_id: int,
    condition_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_member(db, user, member_id)
    condition = (
        db.query(MedicalCondition)
        .filter(
            MedicalCondition.id == condition_id,
            MedicalCondition.family_member_id == member_id,
        )
        .first()
    )
    if not condition:
        raise HTTPException(status_code=404, detail="Condition not found")
    db.delete(condition)
    db.commit()


@router.post("/{member_id}/medications", response_model=MedicationOut, status_code=201)
def add_medication(
    member_id: int,
    payload: MedicationIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _get_member(db, user, member_id)
    medication = Medication(family_member_id=member.id, **payload.model_dump())
    db.add(medication)
    db.commit()
    db.refresh(medication)
    return medication


@router.delete("/{member_id}/medications/{medication_id}", status_code=204)
def delete_medication(
    member_id: int,
    medication_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_member(db, user, member_id)
    medication = (
        db.query(Medication)
        .filter(Medication.id == medication_id, Medication.family_member_id == member_id)
        .first()
    )
    if not medication:
        raise HTTPException(status_code=404, detail="Medication not found")
    db.delete(medication)
    db.commit()
