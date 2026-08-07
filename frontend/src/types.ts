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
}

export interface RecommendationResponse {
  plans: PlanCost[];
  recommended_plan_id: string;
  lowest_expected_cost_plan_id: string;
  best_worst_case_plan_id: string;
  explanation: string;
}
