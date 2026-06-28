import { Component, inject, OnInit, Output, EventEmitter, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { TranslateModule } from '@ngx-translate/core';
import { catchError, finalize, of, timeout, switchMap } from 'rxjs';
import { CsrPlansApi } from '../api/csr-plans-api';
import type { CreateCsrPlanPayload } from '../models/csr-plan.model';
import { SitesApi, type Site } from '@features/site-management/api/sites-api';
import { AuthApi } from '@features/user-management/login/auth-api';
import { AuthStore } from '@core/services/auth-store';

const LOAD_TIMEOUT_MS = 8000;

@Component({
  selector: 'app-plan-create-sidebar',
  standalone: true,
  imports: [ReactiveFormsModule, CommonModule, TranslateModule],
  templateUrl: './plan-create-sidebar.html',
  host: { class: 'flex flex-col flex-1 min-h-0 overflow-hidden block w-full' },
})
export class PlanCreateSidebarComponent implements OnInit {
  private fb = inject(FormBuilder);
  private cdr = inject(ChangeDetectorRef);
  private csrPlansApi = inject(CsrPlansApi);
  private sitesApi = inject(SitesApi);
  private authApi = inject(AuthApi);
  private authStore = inject(AuthStore);

  @Output() closed = new EventEmitter<void>();
  @Output() created = new EventEmitter<void>();

  planForm!: FormGroup;
  sites: Site[] = [];
  loading = false;
  currentYear = new Date().getFullYear();
  loadingSites = true;

  ngOnInit(): void {
    this.planForm = this.fb.group({
      site_id: ['', Validators.required],
      year: [new Date().getFullYear(), [Validators.required, Validators.min(2000), Validators.max(2100)]],
      validation_mode: ['101'],
      total_hc: [null as number | null],
    });
    this.loadSites();
  }

  private mapProfileSitesToSites(profile: { sites?: Array<{ site_id: string; site_name?: string | null; site_code?: string | null }> }): Site[] {
    if (!profile?.sites?.length) return [];
    return profile.sites.map((s) => ({
      id: s.site_id,
      name: s.site_name ?? s.site_code ?? 'Site',
      code: s.site_code ?? '',
      region: '',
      country: '',
      location: '',
      description: '',
      is_active: true,
      created_at: null,
      updated_at: null,
    }));
  }

  private loadSites(): void {
    this.loadingSites = true;
    this.cdr.markForCheck();
    const isSiteUser = this.authStore.userRole() === 'site';
    this.authApi.getProfile().pipe(
      timeout(LOAD_TIMEOUT_MS),
      catchError(() => of(null)),
    ).pipe(
      switchMap((profile) => {
        const fromProfile = this.mapProfileSitesToSites(profile ?? {});
        if (fromProfile.length > 0) return of({ sites: fromProfile });
        if (isSiteUser) return of({ sites: [] as Site[] });
        return this.sitesApi.list().pipe(
          timeout(LOAD_TIMEOUT_MS),
          catchError(() => of([] as Site[])),
          switchMap((list) => of({ sites: Array.isArray(list) ? list : [] })),
        );
      }),
      finalize(() => {
        this.loadingSites = false;
        this.cdr.markForCheck();
      }),
    ).subscribe((result) => {
      this.sites = result.sites;
      this.cdr.markForCheck();
    });
  }

  close(): void {
    this.closed.emit();
  }

  submit(): void {
    if (this.loading || this.planForm.invalid) return;
    this.loading = true;
    this.cdr.markForCheck();
    const raw = this.planForm.getRawValue();
    const selectedMode = ['101', '111', '211', '311'].includes(String(raw.validation_mode))
      ? (raw.validation_mode as '101' | '111' | '211' | '311')
      : '101';
    const payload: CreateCsrPlanPayload = {
      site_id: raw.site_id,
      year: Number(raw.year),
      validation_mode: selectedMode,
      total_hc: raw.total_hc != null && raw.total_hc !== '' ? Number(raw.total_hc) : null,
    };
    this.csrPlansApi.create(payload).pipe(
      finalize(() => {
        this.loading = false;
        this.cdr.markForCheck();
      }),
    ).subscribe({
      next: () => {
        this.created.emit();
        this.closed.emit();
      },
      error: () => {},
    });
  }
}
