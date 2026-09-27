export interface UserOut {
  id: number;
  email: string;
  full_name: string;
}

export interface Condition {
  id: number;
  name: string;
  notes?: string | null;
  ongoing: boolean;
}

export interface Medication {
  id: number;
  name: string;
  is_generic: boolean;
  fills_per_year: number;
}

export interface FamilyMember {
  id: number;
  name: string;
  relation: string;
  age?: number | null;
  expected_primary_care_visits: number;
  expected_specialist_visits: number;
  expected_er_visits: number;
  expected_generic_prescriptions: number;
  expected_brand_prescriptions: number;
  planned_procedure_cost: number;
  conditions: Condition[];
  medications: Medication[];
}

export interface Expense {
  id: number;
  category: string;
  amount: number;
  description?: string | null;
  incurred_on?: string | null;
}

export interface DocumentOut {
  id: number;
  filename: string;
  content_type?: string | null;
  expenses: Expense[];
}

export interface ExpenseSummary {
  category: string;
  total: number;
}

export type AccessSeverity = "blocking" | "high" | "medium" | "low";

export interface AccessFinding {
  severity: AccessSeverity;
  type: string;
  service_name: string;
  pathway_name: string;
  message: string;
  uncovered_cost: number;
}

export interface PlanCost {
  plan_id: string;
  plan_name: string;
  plan_type: string;
  annual_premium: number;
  expected_out_of_pocket: number;
  expected_total_cost: number;
  best_case_total_cost: number;
  worst_case_total_cost: number;
  breakdown: Record<string, number>;
  notes: string;
  requires_referral: boolean;
  out_of_network_coverage: boolean;
  access_score: number;
  access_findings: AccessFinding[];
  access_gap_cost: number;
  has_blocking_barrier: boolean;
  access_adjusted_total_cost: number;
}

export interface PathwayService {
  name: string;
  service_type: string;
  annual_quantity: number;
  unit_cost: number;
  clinical_note?: string | null;
}

export interface MatchedPathway {
  id: string;
  name: string;
  category: string;
  summary: string;
  matched_from: string;
  services: PathwayService[];
}

export interface PathwayOption {
  id: string;
  name: string;
  category: string;
  summary: string;
}

export interface RecommendationResponse {
  plans: PlanCost[];
  recommended_plan_id: string;
  lowest_expected_cost_plan_id: string;
  best_worst_case_plan_id: string;
  explanation: string;
  matched_pathways: MatchedPathway[];
  projected_pathway_cost: number;
}

// ---- Practice builder & simulator ----

export interface ProviderInput {
  role: string;
  count: number;
  annual_salary: number;
  clinic_days_per_week: number;
  visits_per_day: number;
  start_month: number;
}

export interface StaffInput {
  role: string;
  count: number;
  annual_salary: number;
  start_month: number;
}

export interface PayerInput {
  payer: string;
  share_pct: number;
  rate_pct_of_medicare: number;
  denial_pct: number;
  days_to_pay: number;
}

export interface PracticeConfig {
  name: string;
  specialty: string;
  months: number;
  open_days_per_week: number;
  exam_rooms: number;
  visits_per_room_per_day: number;
  providers: ProviderInput[];
  staff: StaffInput[];
  benefits_load_pct: number;
  demand: {
    starting_panel: number;
    new_patients_per_month: number;
    ramp_months: number;
    visits_per_patient_per_year: number;
    annual_attrition_pct: number;
    no_show_pct: number;
  };
  revenue: {
    medicare_allowed_per_visit: number;
    billing_mode: "in_house" | "outsourced";
    outsourced_fee_pct: number;
    claims_per_biller_per_month: number;
    denial_recovery_pct: number;
  };
  payer_mix: PayerInput[];
  overhead: {
    rent_per_month: number;
    software_per_provider_per_month: number;
    malpractice_per_provider_per_year: number;
    supplies_per_visit: number;
    marketing_per_month: number;
    other_fixed_per_month: number;
  };
  startup: {
    buildout_and_equipment: number;
    pre_opening_expenses: number;
    owner_equity: number;
    loan_amount: number;
    loan_annual_rate_pct: number;
    loan_term_months: number;
  };
}

export interface PracticeTemplate {
  id: string;
  name: string;
  summary: string;
  config: PracticeConfig;
}

export interface SavedPractice {
  id: number;
  name: string;
  config: PracticeConfig;
  updated_at: string | null;
}

export interface SimMonth {
  month: number;
  active_patients: number;
  new_patients: number;
  turned_away: number;
  capacity_visits: number;
  completed_visits: number;
  utilization_pct: number;
  billed: number;
  collections: number;
  payroll: number;
  occupancy: number;
  other_expenses: number;
  total_expenses: number;
  operating_income: number;
  debt_service: number;
  net_cash_flow: number;
  cash_balance: number;
  accounts_receivable: number;
  days_in_ar: number;
}

export interface SimYear {
  year: number;
  visits: number;
  collections: number;
  expenses: number;
  operating_income: number;
  net_cash_flow: number;
  operating_margin_pct: number;
}

export interface SimPayer {
  payer: string;
  share_pct: number;
  net_per_visit: number;
  visits: number;
  collections: number;
  lost_to_denials: number;
}

export interface SimInsight {
  severity: "blocking" | "high" | "medium" | "low" | "good";
  title: string;
  detail: string;
}

export interface SensitivityRow {
  driver: string;
  low_label: string;
  high_label: string;
  low_value: number;
  high_value: number;
}

export interface SimulationResult {
  summary: {
    starting_cash: number;
    operating_breakeven_month: number | null;
    cash_payback_month: number | null;
    lowest_cash: number;
    lowest_cash_month: number;
    ending_cash: number;
    steady_state_visits_per_month: number;
    steady_state_utilization_pct: number;
    steady_state_collections_per_month: number;
    steady_state_operating_margin_pct: number;
    net_collection_per_visit: number;
    overhead_ratio_pct: number;
    bottleneck: "demand" | "providers" | "rooms";
    final_year_operating_income: number;
  };
  months: SimMonth[];
  years: SimYear[];
  payers: SimPayer[];
  insights: SimInsight[];
  sensitivity: SensitivityRow[];
}
