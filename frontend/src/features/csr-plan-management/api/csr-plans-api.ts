/**
 * CSR Plans API – list and create plans (csr_plans table).
 */
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams, HttpRequest, HttpEventType } from '@angular/common/http';
import { Observable } from 'rxjs';
import { filter, map, tap } from 'rxjs/operators';
import type { CsrPlan } from '../models/csr-plan.model';
import type { CreateCsrPlanPayload, UpdateCsrPlanPayload } from '../models/csr-plan.model';

export interface CsrPlanActivityDetail {
  id: string;
  activity_number: string;
  title: string;
  description?: string;
  status?: string;
  category_name?: string;
  collaboration_nature?: string;
  organization?: string;
  contract_type?: string;
  organizer?: string;
  edition?: number | null;
  start_year?: number | null;
  external_partner_name?: string | null;
  planned_budget?: number | null;
  planned_volunteers?: number | null;
  action_impact_target?: number | null;
  action_impact_unit?: string;
  realized_budget?: number | null;
  participants?: number | null;
  total_hc?: number | null;
  percentage_employees?: number | null;
  number_external_partners?: number | null;
  action_impact_actual?: number | null;
  action_impact_unit_realized?: string;
  /** True if this activity was added during the last change-request unlock period. */
  added_during_unlock?: boolean;
  /** True if this activity was modified during the last change-request unlock period. */
  modified_during_unlock?: boolean;
  /** True if this activity can be edited (plan or activity individually unlocked). */
  activity_editable?: boolean;
  /** Declared outside the annual plan; only realized data was captured at creation. */
  is_off_plan?: boolean;
  off_plan_validation_mode?: string | null;
  off_plan_validation_step?: number | null;
  /** Off-plan activity awaiting validation (SUBMITTED) — current user may approve/reject. */
  can_approve_off_plan?: boolean;
  can_reject_off_plan?: boolean;
  /** In-plan activity individually unlocked on a validated plan — user may submit changes for approval. */
  can_submit_modification_review?: boolean;
  /** After rejection of an in-plan modification review — user may resubmit. */
  can_resubmit_modification_review?: boolean;
  /** At least one realization row exists for this activity (including draft). */
  has_realization?: boolean;
  /** Newest realization row id (same ordering as aggregated realized fields). */
  primary_realization_id?: string | null;
}

export interface CsrPlanDetail extends CsrPlan {
  activities?: CsrPlanActivityDetail[];
  can_approve?: boolean;
  can_reject?: boolean;
  /** Current user's grade on this plan's site (e.g. level_0, level_1); corporate users get null. */
  viewer_site_grade?: string | null;
}

@Injectable({ providedIn: 'root' })
export class CsrPlansApi {
  private apiUrl = '/api';

  constructor(private http: HttpClient) {}

  /**
   * List CSR plans. Optional filters: site_id, year, status.
   * SITE_USER only receives plans for their assigned sites.
   */
  list(params?: { site_id?: string; year?: number; status?: string }): Observable<CsrPlan[]> {
    let httpParams = new HttpParams();
    if (params?.site_id) httpParams = httpParams.set('site_id', params.site_id);
    if (params?.year != null) httpParams = httpParams.set('year', params.year.toString());
    if (params?.status) httpParams = httpParams.set('status', params.status);
    return this.http.get<CsrPlan[]>(`${this.apiUrl}/csr-plans`, { params: httpParams });
  }

  /**
   * Create a new plan (status DRAFT). Requires site_id and year.
   */
  create(payload: CreateCsrPlanPayload): Observable<CsrPlan> {
    return this.http.post<CsrPlan>(`${this.apiUrl}/csr-plans`, payload);
  }

  /**
   * Update a plan (DRAFT or REJECTED only). Editable: year, validation_mode.
   */
  update(planId: string, payload: UpdateCsrPlanPayload): Observable<CsrPlan> {
    return this.http.patch<CsrPlan>(`${this.apiUrl}/csr-plans/${planId}`, payload);
  }

  get(planId: string): Observable<CsrPlanDetail> {
    return this.http.get<CsrPlanDetail>(`${this.apiUrl}/csr-plans/${planId}`);
  }

  submitForValidation(planId: string): Observable<CsrPlan> {
    return this.http.patch<CsrPlan>(`${this.apiUrl}/csr-plans/${planId}/submit`, {});
  }

  approve(planId: string): Observable<CsrPlan> {
    return this.http.patch<CsrPlan>(`${this.apiUrl}/csr-plans/${planId}/approve`, {});
  }

  reject(planId: string, payload: { comment: string; activity_ids?: string[] }): Observable<CsrPlan> {
    const body: { comment: string; activity_ids?: string[] } = { comment: payload.comment };
    if (payload.activity_ids?.length) body.activity_ids = payload.activity_ids;
    return this.http.patch<CsrPlan>(`${this.apiUrl}/csr-plans/${planId}/reject`, body);
  }

  /**
   * Delete a plan (DRAFT or REJECTED only). Activities are cascade-deleted.
   */
  delete(planId: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/csr-plans/${planId}`);
  }

  /** Bulk submit plans (DRAFT → SUBMITTED). */
  bulkSubmit(planIds: string[]): Observable<BulkActionResult> {
    return this.http.post<BulkActionResult>(`${this.apiUrl}/csr-plans/bulk-submit`, { plan_ids: planIds });
  }

  /** Bulk delete plans (DRAFT or REJECTED only). */
  bulkDelete(planIds: string[]): Observable<BulkActionResult> {
    return this.http.post<BulkActionResult>(`${this.apiUrl}/csr-plans/bulk-delete`, { plan_ids: planIds });
  }

  /**
   * Preview Excel import: returns list of plans (site_id, site_name, year) that would be created. No DB write.
   * Optional onProgress(0-100) callback for upload progress.
   */
  importExcelPreview(file: File, options?: { site_id?: string; year?: number; onProgress?: (percent: number) => void }): Observable<ImportPreviewResponse> {
    const form = new FormData();
    form.append('file', file);
    if (options?.site_id) form.append('site_id', options.site_id);
    if (options?.year != null) form.append('year', String(options.year));
    const req = new HttpRequest('POST', `${this.apiUrl}/csr-plans/import-excel-preview`, form, { reportProgress: true });
    return this.http.request<ImportPreviewResponse>(req).pipe(
      tap((event) => {
        if (options?.onProgress) {
          if (event.type === HttpEventType.UploadProgress && event.total && event.total > 0) {
            options.onProgress(Math.round((100 * event.loaded) / event.total));
          } else if (event.type === HttpEventType.Sent) {
            options.onProgress(5); // Upload started
          }
        }
      }),
      filter((event) => event.type === HttpEventType.Response),
      map((event) => (event as any).body),
    );
  }

  /**
   * Check which rows have activity_number conflicts (activity already exists in plan).
   */
  importExcelCheckConflicts(rows: ImportPreviewRow[], options?: { site_id?: string; year?: number }): Observable<ImportCheckConflictsResponse> {
    return this.http.post<ImportCheckConflictsResponse>(`${this.apiUrl}/csr-plans/import-excel-check-conflicts`, {
      rows,
      site_id: options?.site_id,
      year: options?.year,
    });
  }

  /**
   * Re-validate current rows (region, country, site). Returns updated errors so user can proceed when fixed.
   */
  importValidateRows(rows: ImportPreviewRow[], options?: { year?: number }): Observable<{ errors: string[] }> {
    return this.http.post<{ errors: string[] }>(`${this.apiUrl}/csr-plans/import-validate-rows`, {
      rows,
      year: options?.year,
    });
  }

  /**
   * Upload an Excel file and create plans/activities. validation_modes: mode per plan (required when using preview flow).
   * rows: edited rows from preview (optional). If provided, these are used instead of re-parsing the file.
   * Optional onProgress(0-100) callback for upload progress.
   */
  importExcel(
    file: File,
    options?: {
      site_id?: string;
      year?: number;
      validation_modes?: Array<{ site_id: string; year: number; validation_mode: '101' | '111' | '211' | '311' }>;
      rows?: ImportPreviewRow[];
      duplicate_strategy?: 'delete' | 'ignore' | 'overwrite';
      onProgress?: (percent: number) => void;
    }
  ): Observable<ImportExcelResponse> {
    const form = new FormData();
    form.append('file', file);
    if (options?.site_id) form.append('site_id', options.site_id);
    if (options?.year != null) form.append('year', String(options.year));
    if (options?.validation_modes?.length) form.append('validation_modes', JSON.stringify(options.validation_modes));
    if (options?.rows?.length) form.append('rows', JSON.stringify(options.rows));
    if (options?.duplicate_strategy) form.append('duplicate_strategy', options.duplicate_strategy);
    const req = new HttpRequest('POST', `${this.apiUrl}/csr-plans/import-excel`, form, { reportProgress: true });
    return this.http.request<ImportExcelResponse>(req).pipe(
      tap((event) => {
        if (options?.onProgress) {
          if (event.type === HttpEventType.UploadProgress && event.total && event.total > 0) {
            options.onProgress(Math.round((100 * event.loaded) / event.total));
          } else if (event.type === HttpEventType.Sent) {
            options.onProgress(5); // Upload started
          }
        }
      }),
      filter((event) => event.type === HttpEventType.Response),
      map((event) => (event as any).body),
    );
  }
}

export interface BulkActionResult {
  message: string;
  success_count: number;
  total: number;
  errors?: Array<{ plan_id: string; error: string }>;
}

export interface ImportPreviewPlan {
  site_id: string;
  site_name?: string | null;
  year: number;
}

/** Editable row from Excel preview. Keys match backend parse_excel_rows output. */
export interface ImportPreviewRow {
  activity_number?: string;
  region?: string;
  country?: string;
  site?: string;
  title?: string;
  category?: string;
  collaboration_nature?: string;
  /** Excel column « Year »: calendar year of the activity edition (not the plan year from step 1). */
  edition_year?: number | string;
  /** @deprecated Old parse key; prefer edition_year */
  excel_template_year?: number | string;
  /** @deprecated Do not use for Excel Year; kept for legacy preview payloads */
  year?: number | string;
  start_year?: number | string;
  edition?: number | string;
  participants?: number | string;
  planned_volunteers?: number | string;
  total_hc?: number | string;
  percentage_employees?: number | string;
  planned_budget?: number | string;
  realized_budget?: number | string;
  impact_target?: number | string;
  impact_actual?: number | string;
  impact_unit?: string;
  organizer?: string;
  external_partner?: string;
  number_external_partners?: number | string;
  [key: string]: unknown;
}

export interface ImportPreviewResponse {
  plans: ImportPreviewPlan[];
  rows?: ImportPreviewRow[];
  errors?: string[];
  message?: string;
  /** Distinct edition years from the Excel « Year » column (not csr plan years). */
  excel_distinct_edition_years?: number[];
  /** @deprecated Same as excel_distinct_edition_years (misleading name). */
  excel_distinct_plan_years?: number[];
}

export interface ImportConflict {
  row_index: number;
  activity_number: string;
  site_name?: string | null;
  year: number;
  next_activity_number: number;
}

export interface ImportCheckConflictsResponse {
  conflicts: ImportConflict[];
}

export interface ImportExcelResponse {
  message: string;
  plans_created: number;
  plans: Array<{ site_id: string; site_name?: string; year: number; plan_id: string }>;
  activities_created: number;
  realized_created: number;
  errors: string[];
  total_rows: number;
}
