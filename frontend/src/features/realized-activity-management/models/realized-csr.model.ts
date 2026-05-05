/**
 * Realized CSR - aligned with realized_csr table.
 */
export interface RealizedCsr {
  id: string;
  activity_id: string;
  activity_title?: string | null;
  activity_number?: string | null;
  activity_description?: string | null;
  category_id?: string | null;
  category_name?: string | null;
  collaboration_nature?: string | null;
  periodicity?: string | null;
  start_year?: number | null;
  edition?: number | null;
  planned_budget?: number | null;
  action_impact_target?: number | null;
  action_impact_unit_target?: string | null;
  action_impact_duration?: string | null;
  organizer?: string | null;
  external_partner_name?: string | null;
  plan_id?: string | null;
  site_name?: string | null;
  /** When false, plan is locked; user must submit a change request to edit/delete this realization. */
  plan_editable?: boolean;
  plan_status?: string | null;
  realized_budget: number | null;
  participants: number | null;
  employees_actual?: number | null;
  total_hc: number | null;
  action_impact_actual: number | null;
  action_impact_unit: string | null;
  actual_action_impact?: number | null;
  corporate_image_improved?: boolean | null;
  incidents_number?: number | null;
  planned_objectives?: string[];
  completed_objectives?: string[];
  realization_date: string | null;
  comment: string | null;
  contact_name: string | null;
  contact_email: string | null;
  contact_department?: string | null;
  created_by: string | null;
  created_at: string | null;
  updated_at?: string | null;
  unlock_until?: string | null;
  unlock_since?: string | null;
  status?: string | null;
  is_off_plan?: number | boolean | null;
  off_plan_validation_mode?: string | null;
  off_plan_validation_step?: number | null;
}

export interface CreateRealizedCsrPayload {
  activity_id: string;
  realized_budget?: number | null;
  participants?: number | null;
  employees_actual?: number | null;
  total_hc?: number | null;
  action_impact_actual?: number | null;
  action_impact_unit?: string | null;
  realization_date?: string | null;
  comment?: string | null;
  completed_objectives?: string[];
  corporate_image_improved?: boolean | null;
  incidents_number?: number | null;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_department?: string | null;
}
