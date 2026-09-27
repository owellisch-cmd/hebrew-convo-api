from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


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


# ---- Practice builder & simulator ----


class ProviderIn(BaseModel):
    role: str
    count: int = Field(1, ge=0, le=50)
    annual_salary: float = Field(ge=0)
    clinic_days_per_week: float = Field(4.5, ge=0, le=7)
    visits_per_day: float = Field(ge=0, le=100)
    start_month: int = Field(1, ge=1, le=120)


class StaffIn(BaseModel):
    role: str
    count: int = Field(1, ge=0, le=200)
    annual_salary: float = Field(ge=0)
    start_month: int = Field(1, ge=1, le=120)


class DemandIn(BaseModel):
    # Patients who follow providers from a previous practice on day one.
    starting_panel: float = Field(0, ge=0)
    new_patients_per_month: float = Field(ge=0)
    ramp_months: int = Field(6, ge=0, le=60)
    visits_per_patient_per_year: float = Field(gt=0, le=60)
    annual_attrition_pct: float = Field(10, ge=0, le=100)
    no_show_pct: float = Field(8, ge=0, le=90)


class RevenueIn(BaseModel):
    medicare_allowed_per_visit: float = Field(gt=0)
    billing_mode: str = Field("in_house", pattern="^(in_house|outsourced)$")
    outsourced_fee_pct: float = Field(6, ge=0, le=30)
    claims_per_biller_per_month: float = Field(1600, gt=0)
    denial_recovery_pct: float = Field(65, ge=0, le=100)


class PayerIn(BaseModel):
    payer: str
    share_pct: float = Field(ge=0, le=100)
    rate_pct_of_medicare: float = Field(ge=0, le=500)
    denial_pct: float = Field(ge=0, le=100)
    days_to_pay: float = Field(ge=0, le=365)


class OverheadIn(BaseModel):
    rent_per_month: float = Field(0, ge=0)
    software_per_provider_per_month: float = Field(0, ge=0)
    malpractice_per_provider_per_year: float = Field(0, ge=0)
    supplies_per_visit: float = Field(0, ge=0)
    marketing_per_month: float = Field(0, ge=0)
    other_fixed_per_month: float = Field(0, ge=0)


class StartupIn(BaseModel):
    buildout_and_equipment: float = Field(0, ge=0)
    pre_opening_expenses: float = Field(0, ge=0)
    owner_equity: float = Field(0, ge=0)
    loan_amount: float = Field(0, ge=0)
    loan_annual_rate_pct: float = Field(8, ge=0, le=40)
    loan_term_months: int = Field(84, ge=1, le=360)


class PracticeConfig(BaseModel):
    name: str = "My practice"
    specialty: str = "custom"
    months: int = Field(36, ge=6, le=120)
    open_days_per_week: float = Field(5, gt=0, le=7)
    exam_rooms: int = Field(ge=1, le=100)
    visits_per_room_per_day: float = Field(gt=0, le=100)
    providers: list[ProviderIn] = Field(min_length=1)
    staff: list[StaffIn] = []
    benefits_load_pct: float = Field(22, ge=0, le=100)
    demand: DemandIn
    revenue: RevenueIn
    payer_mix: list[PayerIn] = Field(min_length=1)
    overhead: OverheadIn
    startup: StartupIn

    @model_validator(mode="after")
    def _payer_mix_sums_to_100(self):
        total = sum(p.share_pct for p in self.payer_mix)
        if abs(total - 100) > 0.5:
            raise ValueError(f"Payer mix shares must add up to 100% (currently {total:g}%)")
        return self


class PracticeTemplate(BaseModel):
    id: str
    name: str
    summary: str
    config: PracticeConfig


class PracticeIn(BaseModel):
    name: str
    config: PracticeConfig


class PracticeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    config: PracticeConfig
    updated_at: datetime | None = None


class MonthResult(BaseModel):
    month: int
    active_patients: float
    new_patients: float
    turned_away: float
    capacity_visits: float
    completed_visits: float
    utilization_pct: float
    billed: float
    collections: float
    payroll: float
    occupancy: float
    other_expenses: float
    total_expenses: float
    operating_income: float
    debt_service: float
    net_cash_flow: float
    cash_balance: float
    accounts_receivable: float
    days_in_ar: float


class YearSummary(BaseModel):
    year: int
    visits: float
    collections: float
    expenses: float
    operating_income: float
    net_cash_flow: float
    operating_margin_pct: float


class PayerResult(BaseModel):
    payer: str
    share_pct: float
    net_per_visit: float
    visits: float
    collections: float
    lost_to_denials: float


class Insight(BaseModel):
    severity: str  # blocking | high | medium | low | good
    title: str
    detail: str


class SensitivityRow(BaseModel):
    driver: str
    low_label: str
    high_label: str
    low_value: float
    high_value: float


class SimulationSummary(BaseModel):
    starting_cash: float
    operating_breakeven_month: int | None
    cash_payback_month: int | None
    lowest_cash: float
    lowest_cash_month: int
    ending_cash: float
    steady_state_visits_per_month: float
    steady_state_utilization_pct: float
    steady_state_collections_per_month: float
    steady_state_operating_margin_pct: float
    net_collection_per_visit: float
    overhead_ratio_pct: float
    bottleneck: str  # demand | providers | rooms
    final_year_operating_income: float


class SimulationResult(BaseModel):
    summary: SimulationSummary
    months: list[MonthResult]
    years: list[YearSummary]
    payers: list[PayerResult]
    insights: list[Insight]
    sensitivity: list[SensitivityRow]
