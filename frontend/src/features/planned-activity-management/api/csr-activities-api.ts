/**
 * CSR Activities API – list and create activities.
 */
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import type { CsrActivity } from '../models/csr-activity.model';

export interface PlannedActivityListItem extends CsrActivity {
  site_id?: string | null;
  site_name?: string | null;
  site_code?: string | null;
  year?: number;
  category_name?: string | null;
  /** Plan status (VALIDATED = locked, no edit/delete). */
  plan_status?: string | null;
  /** When false, plan is locked; user must submit a change request to edit/delete. */
  plan_editable?: boolean;
}

export interface CreateCsrActivityPayload {
  plan_id: string;
  title: string;
  /** When draft=true, category_id and activity_number are optional (backend uses defaults). */
  draft?: boolean;
  category_id?: string;
  activity_number?: string;
  organization?: string | null;
  contract_type?: string | null;
  description?: string | null;
  collaboration_nature?: string | null;
  periodicity?: string | null;
  planned_budget?: number | null;
  action_impact_target?: number | null;
  action_impact_unit?: string | null;
  action_impact_duration?: string | null;
  employees_planned?: number | null;
  planned_objectives?: string[];
  start_year?: number | null;
  edition?: number | null;
  edition_year?: number | null;
  organizer?: string | null;
  external_partner?: string | null;
  external_partners?: string[];
}

/** Off-plan create: activity + realized row; year/month optional (backend defaults to plan year + current month). */
export interface OffPlanRealizationPayload {
  plan_id: string;
  validation_mode: '101' | '111';
  /** Past-year plan flow: when true, save planned fields too. */
  include_planned_details?: boolean;
  activity_number: string;
  title: string;
  organization?: string | null;
  contract_type?: string | null;
  description?: string | null;

  category_id: string;
  collaboration_nature?: string | null;
  consumed_budget?: number | null;
  action_impact_target?: number | null;
  action_impact_unit?: string | null;
  action_impact_duration?: string | null;
  employees_planned?: number | null;
  planned_objectives?: string[];
  start_year?: number | null;
  edition?: number | null;
  edition_year?: number | null;
  external_partner?: string | null;
  external_partners?: string[];

  /** Defaults on server if omitted. */
  year?: number;
  month?: number;

  realized_budget?: number | null;
  participants?: number | null;
  employees_actual?: number | null;
  total_hc?: number | null;
  action_impact_actual?: number | null;
  action_impact_unit_realized?: string | null;
  organizer?: string | null;
  /** ISO date string YYYY-MM-DD for realized_csr.realization_date */
  realization_date?: string | null;
  comment?: string | null;
  completed_objectives?: string[];
  corporate_image_improved?: boolean | null;
  incidents_number?: number | null;
  contact_department?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
}

export interface OffPlanRealizationResponse {
  activity: CsrActivity & { site_id?: string };
  realization: { id: string; activity_id: string };
}

@Injectable({ providedIn: 'root' })
export class CsrActivitiesApi {
  private apiUrl = '/api';

  constructor(private http: HttpClient) {}

  /** List with optional plan_id and year. Backend returns site_name, year, category_name for list view. */
  list(params?: { plan_id?: string; year?: number; exclude_realized?: boolean }): Observable<PlannedActivityListItem[]> {
    let httpParams = new HttpParams();
    if (params?.plan_id) httpParams = httpParams.set('plan_id', params.plan_id);
    if (params?.year != null) httpParams = httpParams.set('year', params.year.toString());
    if (params?.exclude_realized === true) httpParams = httpParams.set('exclude_realized', '1');
    if (params?.exclude_realized === false) httpParams = httpParams.set('exclude_realized', '0');
    return this.http.get<PlannedActivityListItem[]>(`${this.apiUrl}/csr-activities`, { params: httpParams });
  }

  get(id: string): Observable<PlannedActivityListItem> {
    return this.http.get<PlannedActivityListItem>(`${this.apiUrl}/csr-activities/${id}`);
  }

  create(payload: CreateCsrActivityPayload): Observable<CsrActivity> {
    return this.http.post<CsrActivity>(`${this.apiUrl}/csr-activities`, payload);
  }

  createOffPlanRealization(payload: OffPlanRealizationPayload): Observable<OffPlanRealizationResponse> {
    return this.http.post<OffPlanRealizationResponse>(`${this.apiUrl}/csr-activities/off-plan-realization`, payload);
  }

  /**
   * Plan d’année passée modifiable : activité DRAFT + realized_csr (pas hors plan, pas de validation par activité).
   * Même corps utile que l’off-plan ; validation_mode est ignoré côté serveur.
   */
  createPlanRealizedDraftWithRealization(
    payload: OffPlanRealizationPayload,
  ): Observable<OffPlanRealizationResponse> {
    return this.http.post<OffPlanRealizationResponse>(`${this.apiUrl}/csr-activities/plan-realized-draft`, payload);
  }

  update(id: string, payload: UpdateCsrActivityPayload): Observable<CsrActivity> {
    return this.http.put<CsrActivity>(`${this.apiUrl}/csr-activities/${id}`, payload);
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/csr-activities/${id}`);
  }

  /** Approve off-plan activity (workflow 101 / 111). */
  approveOffPlan(activityId: string): Observable<CsrActivity> {
    return this.http.patch<CsrActivity>(`${this.apiUrl}/csr-activities/${activityId}/approve`, {});
  }

  /** Reject off-plan activity (motif obligatoire). */
  rejectOffPlan(activityId: string, payload: { comment: string }): Observable<CsrActivity> {
    return this.http.patch<CsrActivity>(`${this.apiUrl}/csr-activities/${activityId}/reject`, {
      comment: payload.comment,
    });
  }

  /** After corporate/site L1 rejection: resubmit for validation. */
  resubmitOffPlan(activityId: string, payload?: { validation_mode?: '101' | '111' }): Observable<CsrActivity> {
    return this.http.patch<CsrActivity>(`${this.apiUrl}/csr-activities/${activityId}/resubmit-off-plan`, payload ?? {});
  }

  /** Submit changes for an individually unlocked in-plan activity (validated plan, no plan-level unlock). */
  submitModificationReview(activityId: string): Observable<CsrActivity> {
    return this.http.patch<CsrActivity>(
      `${this.apiUrl}/csr-activities/${activityId}/submit-modification-review`,
      {},
    );
  }
}

export interface UpdateCsrActivityPayload {
  category_id: string;
  activity_number: string;
  title: string;
  organization?: string | null;
  contract_type?: string | null;
  description?: string | null;
  collaboration_nature?: string | null;
  periodicity?: string | null;
  planned_budget?: number | null;
  action_impact_target?: number | null;
  action_impact_unit?: string | null;
  action_impact_duration?: string | null;
  employees_planned?: number | null;
  planned_objectives?: string[];
  organizer?: string | null;
  edition?: number | null;
  edition_year?: number | null;
  start_year?: number | null;
  external_partner?: string | null;
}
