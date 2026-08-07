from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    family_members = relationship(
        "FamilyMember", back_populates="owner", cascade="all, delete-orphan"
    )
    documents = relationship(
        "Document", back_populates="owner", cascade="all, delete-orphan"
    )


class FamilyMember(Base):
    __tablename__ = "family_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    relation = Column(String, nullable=False)  # self, spouse, child, other
    age = Column(Integer, nullable=True)

    # Self-reported expected annual utilization — drives the cost simulation
    expected_primary_care_visits = Column(Integer, default=0)
    expected_specialist_visits = Column(Integer, default=0)
    expected_er_visits = Column(Integer, default=0)
    expected_generic_prescriptions = Column(Integer, default=0)
    expected_brand_prescriptions = Column(Integer, default=0)
    planned_procedure_cost = Column(Float, default=0)  # e.g. surgery, maternity

    owner = relationship("User", back_populates="family_members")
    conditions = relationship(
        "MedicalCondition", back_populates="family_member", cascade="all, delete-orphan"
    )
    medications = relationship(
        "Medication", back_populates="family_member", cascade="all, delete-orphan"
    )


class MedicalCondition(Base):
    __tablename__ = "medical_conditions"

    id = Column(Integer, primary_key=True, index=True)
    family_member_id = Column(Integer, ForeignKey("family_members.id"), nullable=False)
    name = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    ongoing = Column(Boolean, default=True)

    family_member = relationship("FamilyMember", back_populates="conditions")


class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    family_member_id = Column(Integer, ForeignKey("family_members.id"), nullable=False)
    name = Column(String, nullable=False)
    is_generic = Column(Boolean, default=True)
    fills_per_year = Column(Integer, default=12)

    family_member = relationship("FamilyMember", back_populates="medications")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="documents")
    expenses = relationship(
        "Expense", back_populates="document", cascade="all, delete-orphan"
    )


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    category = Column(String, nullable=False)  # primary_care, specialist, er, hospital, prescription, other
    amount = Column(Float, nullable=False)
    description = Column(String, nullable=True)
    incurred_on = Column(String, nullable=True)  # free-text date from source data

    document = relationship("Document", back_populates="expenses")
