/**
 * AuthApi - HTTP client for /api/auth endpoints.
 * Handles login, logout, session validation, profile, and password change.
 */
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

/** Response from POST /api/auth/login */
export interface LoginResponse {
  token: string;
  email: string;
  role: string; // SITE_USER | CORPORATE_USER from backend
  level?: string | null;
  user_id?: string | number;
  first_name?: string | null;
  last_name?: string | null;
  avatar_url?: string | null;
  permissions?: { keys?: string[] } | null;
  expires_at?: string;
}

/** Response from GET /api/auth/me - minimal user info for session validation */
export interface MeResponse {
  user_id: string | number;
  email: string;
  role: string;
  level?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  avatar_url?: string | null;
  permissions?: { keys?: string[] } | null;
}

/** Site assignment in profile (SITE_USER only) */
export interface ProfileSite {
  id: string;
  site_id: string;
  site_name: string | null;
  site_code: string | null;
  granted_at: string | null;
}

/** Response from GET /api/auth/profile - full user profile */
export interface ProfileResponse {
  id: string;
  first_name: string | null;
  last_name: string | null;
  phone: string | null;
  language: 'fr' | 'en';
  theme: 'light' | 'dark';
  notifications: {
    csr_plan_validation: boolean;
    activity_validation: boolean;
    activity_reminders: boolean;
    weekly_summary_email: boolean;
  };
  email: string;
  role: string;
  is_active: boolean;
  created_at: string | null;
  last_login: string | null;
  avatar_url: string | null;
  sites: ProfileSite[];
}

@Injectable({ providedIn: 'root' })
export class AuthApi {
  private apiUrl = '/api';

  constructor(private http: HttpClient) {}

  login(email: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.apiUrl}/auth/login`, {
      email,
      password,
    });
 
  }

  logout(): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.apiUrl}/auth/logout`, {});
  }

  getMe(): Observable<MeResponse> {
    return this.http.get<MeResponse>(`${this.apiUrl}/auth/me`);
  }

  /** Fetch full profile of the current user (requires auth) */
  getProfile(): Observable<ProfileResponse> {
    return this.http.get<ProfileResponse>(`${this.apiUrl}/auth/profile`);
  }

  /** Update editable profile fields for current user. Supports partial updates. */
  updateProfile(payload: {
    first_name?: string;
    last_name?: string;
    phone?: string | null;
    language?: 'fr' | 'en';
    theme?: 'light' | 'dark';
    notifications?: {
      csr_plan_validation?: boolean;
      activity_validation?: boolean;
      activity_reminders?: boolean;
      weekly_summary_email?: boolean;
    };
  }): Observable<ProfileResponse> {
    return this.http.put<ProfileResponse>(`${this.apiUrl}/auth/profile`, payload);
  }

  /** Change current user's password. Requires current password and new password (min 8 chars). */
  changePassword(currentPassword: string, newPassword: string): Observable<{ message: string }> {
    return this.http.put<{ message: string }>(`${this.apiUrl}/auth/change-password`, {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }

  /** Upload profile photo. Returns new avatar_url. */
  uploadProfilePhoto(file: File): Observable<{ message: string; avatar_url: string }> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<{ message: string; avatar_url: string }>(`${this.apiUrl}/auth/profile-photo`, formData);
  }
}
