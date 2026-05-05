/** CSR Activity - aligned with csr_activities table (for dropdown). */
export interface CsrActivity {
  id: string;
  plan_id: string;
  activity_number: string;
  title: string;
  organization?: string | null;
  contract_type?: string | null;
  description?: string | null;
  category_id?: string;
  status?: string;
  /** When plan is VALIDATED/LOCKED: lifecycle / review label (COMPLETED, IN_PROGRESS, PLANNED, UNDER_REVIEW, REJECTED). */
  effective_status?: string | null;
  is_off_plan?: boolean;
  planned_budget?: number | null;
  collaboration_nature?: string | null;
  periodicity?: string | null;
  organizer?: string | null;
  action_impact_target?: number | null;
  action_impact_unit?: string | null;
  action_impact_duration?: string | null;
  edition?: number | null;
  edition_year?: number | null;
  start_year?: number | null;
  employees_planned?: number | null;
  planned_objectives?: string[];
  completed_objectives?: string[];
  external_partner_name?: string | null;
  off_plan_validation_mode?: string | null;
  off_plan_validation_step?: number | null;
}
