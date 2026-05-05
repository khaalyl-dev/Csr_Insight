/**
 * Change Requests API – create, list, get, approve, reject.
 */
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import type { ChangeRequest } from '../models/change-request.model';

export interface ChangeRequestWithDocs extends ChangeRequest {
  documents?: { id: string; file_name: string; file_path: string; file_type: string; uploaded_at: string | null }[];
  plan_site_name?: string;
  plan_year?: number;
  plan_id?: string;
  activity_title?: string;
  activity_number?: string;
  requested_by_name?: string;
  requested_by_avatar_url?: string | null;
  requested_duration?: string | null;
  reviewed_by_name?: string;
  reviewed_by_avatar_url?: string | null;
  site_name?: string;
  pending_item_type?: 'CHANGE_REQUEST' | 'OFF_PLAN_ACTIVITY' | 'IN_PLAN_ACTIVITY_MOD' | 'PLAN_VALIDATION';
  activity_id?: string;
  off_plan_validation_mode?: string | null;
  validation_mode?: string | null;
  validation_step?: number | null;
}

@Injectable({ providedIn: 'root' })
export class ChangeRequestsApi {
  private apiUrl = '/api';

  constructor(private http: HttpClient) {}

  create(payload: {
    plan_id?: string;
    activity_id?: string;
    reason: string;
    requested_duration?: number;
    /** Required for site level 0 (not level 1): 101 or 111 */
    validation_mode?: '101' | '111';
  }): Observable<ChangeRequestWithDocs> {
    return this.http.post<ChangeRequestWithDocs>(`${this.apiUrl}/change-requests`, payload);
  }

  list(params?: { status?: string }): Observable<ChangeRequestWithDocs[]> {
    let httpParams = new HttpParams();
    if (params?.status) httpParams = httpParams.set('status', params.status);
    return this.http.get<ChangeRequestWithDocs[]>(`${this.apiUrl}/change-requests`, { params: httpParams });
  }

  get(id: string): Observable<ChangeRequestWithDocs> {
    return this.http.get<ChangeRequestWithDocs>(`${this.apiUrl}/change-requests/${id}`);
  }

  approve(id: string): Observable<ChangeRequestWithDocs> {
    return this.http.post<ChangeRequestWithDocs>(`${this.apiUrl}/change-requests/${id}/approve`, {});
  }

  reject(id: string, comment?: string): Observable<ChangeRequestWithDocs> {
    return this.http.post<ChangeRequestWithDocs>(`${this.apiUrl}/change-requests/${id}/reject`, { comment: comment ?? '' });
  }
}
