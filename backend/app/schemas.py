from pydantic import BaseModel, EmailStr, ConfigDict


# ---- Auth ----


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Medical conditions / medications ----


class ConditionIn(BaseModel):
    name: str
    notes: str | None = None
    ongoing: bool = True


class ConditionOut(ConditionIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class MedicationIn(BaseModel):
    name: str
    is_generic: bool = True
    fills_per_year: int = 12


class MedicationOut(MedicationIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---- Family members ----


class FamilyMemberIn(BaseModel):
    name: str
    relation: str
    age: int | None = None
    expected_primary_care_visits: int = 0
    expected_specialist_visits: int = 0
    expected_er_visits: int = 0
    expected_generic_prescriptions: int = 0
    expected_brand_prescriptions: int = 0
    planned_procedure_cost: float = 0


class FamilyMemberOut(FamilyMemberIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    conditions: list[ConditionOut] = []
    medications: list[MedicationOut] = []


# ---- Expenses / documents ----


class ExpenseIn(BaseModel):
    category: str
    amount: float
    description: str | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: str
    amount: float
    description: str | None = None
    incurred_on: str | None = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    content_type: str | None = None
    expenses: list[ExpenseOut] = []


class ExpenseSummary(BaseModel):
    category: str
    total: float


# ---- Recommendation ----


class AccessFinding(BaseModel):
    severity: str  # blocking | high | medium | low
    type: str
    service_name: str
    pathway_name: str
    message: str
    uncovered_cost: float


class PlanCost(BaseModel):
    plan_id: str
    plan_name: str
    plan_type: str
    annual_premium: float
    expected_out_of_pocket: float
    expected_total_cost: float
    best_case_total_cost: float
    worst_case_total_cost: float
    breakdown: dict
    notes: str
    requires_referral: bool
    out_of_network_coverage: bool
    access_score: int = 100
    access_findings: list[AccessFinding] = []
    access_gap_cost: float = 0
    has_blocking_barrier: bool = False
    access_adjusted_total_cost: float = 0


class PathwayServiceOut(BaseModel):
    name: str
    service_type: str
    annual_quantity: int
    unit_cost: float
    clinical_note: str | None = None


class MatchedPathway(BaseModel):
    id: str
    name: str
    category: str
    summary: str
    matched_from: str
    services: list[PathwayServiceOut]


class PathwayOption(BaseModel):
    id: str
    name: str
    category: str
    summary: str


class RecommendationResponse(BaseModel):
    plans: list[PlanCost]
    recommended_plan_id: str
    lowest_expected_cost_plan_id: str
    best_worst_case_plan_id: str
    explanation: str
    matched_pathways: list[MatchedPathway] = []
    projected_pathway_cost: float = 0
