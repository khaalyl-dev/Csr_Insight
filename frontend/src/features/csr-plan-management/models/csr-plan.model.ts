import type { PlanStatus } from '@core/models/enums';

export interface CsrPlan {
  id: string;
  site_id: string;
  site_name?: string | null;
  site_code?: string | null;
  site_region?: string | null;
  site_country?: string | null;
  year: number;
  validation_mode: string;
  status: PlanStatus;
  allocated_budget: number | null;
  total_hc?: number | null;
  budget_consumed?: number | null;
  total_estimated_budget?: number | null;
  rejected_comment?: string | null;
  /** IDs des activités à modifier (plusieurs possibles). */
  rejected_activity_ids?: string[] | null;
  validation_step?: number | null;
  submitted_at: string | null;
  validated_at: string | null;
  /** Date limite de modification (après approbation d'une demande de modification); après cette date le plan redevient verrouillé */
  unlock_until?: string | null;
  created_by: string | null;
  /** User id who last submitted for validation (backend). */
  submitted_by?: string | null;
  /** Display name when status is SUBMITTED (first + last). */
  submitted_by_name?: string | null;
  submitted_by_avatar_url?: string | null;
  created_at: string;
  updated_at: string;
  activities_count?: number;
  /** Planned activities that have at least one realization row (list API). */
  activities_realized_count?: number;
  can_approve?: boolean;
  can_reject?: boolean;
}

export interface CreateCsrPlanPayload {
  site_id: string;
  year: number;
  validation_mode?: '101' | '111' | '211' | '311';
  allocated_budget?: number | null;
  total_hc?: number | null;
}

export interface UpdateCsrPlanPayload {
  year?: number;
  validation_mode?: '101' | '111' | '211' | '311';
  allocated_budget?: number | null;
  total_hc?: number | null;
}
