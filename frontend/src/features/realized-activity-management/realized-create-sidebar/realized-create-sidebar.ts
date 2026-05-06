import { Component, inject, OnInit, Output, EventEmitter, Input, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { TranslateModule } from '@ngx-translate/core';
import { catchError, finalize, of, switchMap, timeout } from 'rxjs';
import { RealizedCsrApi } from '../api/realized-csr-api';
import { CsrActivitiesApi, type PlannedActivityListItem } from '../api/csr-activities-api';
import { CsrPlansApi } from '@features/csr-plan-management/api/csr-plans-api';
import { DocumentsApi } from '@features/file-management/api/documents-api';
import type { CreateRealizedCsrPayload } from '../models/realized-csr.model';
import type { CsrPlan } from '@features/csr-plan-management/models/csr-plan.model';

const LOAD_TIMEOUT_MS = 8000;
// Month/year fields were removed from realized_activity; we now rely on realization_date.

@Component({
  selector: 'app-realized-create-sidebar',
  standalone: true,
  imports: [ReactiveFormsModule, CommonModule, TranslateModule],
  templateUrl: './realized-create-sidebar.html',
  host: {
    class: 'flex flex-col flex-1 min-h-0 overflow-hidden block w-full',
  },
})
export class RealizedCreateSidebarComponent implements OnInit {
  private fb = inject(FormBuilder);
  private cdr = inject(ChangeDetectorRef);
  private realizedApi = inject(RealizedCsrApi);
  private activitiesApi = inject(CsrActivitiesApi);
  private plansApi = inject(CsrPlansApi);
  private documentsApi = inject(DocumentsApi);

  @Input() initialPlanId: string | null = null;
  @Input() initialActivityId: string | null = null;

  @Output() closed = new EventEmitter<void>();
  @Output() created = new EventEmitter<void>();

  form!: FormGroup;
  plans: CsrPlan[] = [];
  editablePlans: CsrPlan[] = [];
  activities: PlannedActivityListItem[] = [];
  plannedObjectives: string[] = [];
  completedObjectives = new Set<string>();
  currentYear = new Date().getFullYear();
  loading = false;
  loadingData = true;
  selectedFiles: File[] = [];
  fileTouched = false;
  submitError = '';

  get selectedPlan(): CsrPlan | null {
    const id = this.form.get('plan_id')?.value;
    return this.plans.find((p) => p.id === id) ?? null;
  }

  /** Date de réalisation : uniquement dans l'année civile du plan sélectionné. */
  get realizationDateMin(): string {
    const y = this.selectedPlan?.year ?? this.currentYear;
    return `${y}-01-01`;
  }

  get realizationDateMax(): string {
    const y = this.selectedPlan?.year ?? this.currentYear;
    return `${y}-12-31`;
  }

  ngOnInit(): void {
    this.form = this.fb.group({
      plan_id: ['', Validators.required],
      activity_id: ['', Validators.required],
      realized_budget: [null as number | null, Validators.required],
      participants: [null as number | null, Validators.required],
      total_hc: [null as number | null],
      action_impact_actual: [null as number | null, Validators.required],
      action_impact_unit: ['', Validators.required],
      realization_date: ['', Validators.required],
      corporate_image_improved: [null as boolean | null, Validators.required],
      incidents_number: [null as number | null, Validators.required],
      organizer: ['', Validators.required],
      external_partner: ['', Validators.required],
      comment: ['', Validators.required],
      contact_name: ['', Validators.required],
      contact_email: ['', [Validators.required, Validators.email]],
      contact_department: ['', Validators.required],
    });

    this.form.get('plan_id')?.valueChanges.subscribe((id) => this.onPlanChange(id));
    this.form.get('activity_id')?.valueChanges.subscribe((id) => this.onActivityChange(id));

    if (this.initialPlanId) {
      this.form.patchValue({ plan_id: this.initialPlanId });
    }

    this.loadData();
  }

  private loadData(): void {
    this.loadingData = true;
    this.cdr.markForCheck();
    this.plansApi.list().pipe(
      timeout(LOAD_TIMEOUT_MS),
      catchError(() => of([] as CsrPlan[])),
      switchMap((plans) => {
        this.plans = Array.isArray(plans) ? plans : [];
        this.editablePlans = this.getEditablePlans(this.plans);
        if (this.initialPlanId && !this.editablePlans.some((p) => p.id === this.initialPlanId)) {
          const initial = this.plans.find((p) => p.id === this.initialPlanId);
          if (initial) {
            this.editablePlans = [initial, ...this.editablePlans];
          }
        }
        return of(null);
      }),
      finalize(() => {
        this.loadingData = false;
        if (this.initialPlanId && this.editablePlans.some((p) => p.id === this.initialPlanId)) {
          this.form.patchValue({ plan_id: this.initialPlanId });
          this.onPlanChange(this.initialPlanId);
        }
        this.cdr.markForCheck();
      }),
    ).subscribe();
  }

  private getEditablePlans(plans: CsrPlan[]): CsrPlan[] {
    const currentYear = new Date().getFullYear();
    return plans
      .filter((p) => p.year >= currentYear - 2 && p.year <= currentYear + 1)
      .sort((a, b) => b.year - a.year || (a.site_name ?? '').localeCompare(b.site_name ?? ''));
  }

  private onPlanChange(planId: string): void {
    this.form.patchValue({ activity_id: '' });
    this.activities = [];
    this.plannedObjectives = [];
    this.completedObjectives.clear();
    if (!planId) {
      this.cdr.markForCheck();
      return;
    }
    const pl = this.plans.find((p) => p.id === planId);
    if (pl) {
      this.form.patchValue({ year: pl.year });
    }
    this.activitiesApi.list({ plan_id: planId, exclude_realized: true }).pipe(
      timeout(LOAD_TIMEOUT_MS),
      catchError(() => of([])),
    ).subscribe((list) => {
      this.activities = Array.isArray(list) ? list : [];
      if (planId === this.initialPlanId && this.initialActivityId && this.activities.some((a) => a.id === this.initialActivityId)) {
        this.form.patchValue({ activity_id: this.initialActivityId });
      }
      this.cdr.markForCheck();
    });
  }

  private onActivityChange(activityId: string): void {
    this.plannedObjectives = [];
    this.completedObjectives.clear();
    if (!activityId) {
      this.cdr.markForCheck();
      return;
    }
    this.activitiesApi.get(activityId).pipe(
      timeout(LOAD_TIMEOUT_MS),
      catchError(() => of(null)),
    ).subscribe((activity) => {
      const list = Array.isArray(activity?.planned_objectives) ? activity.planned_objectives : [];
      this.plannedObjectives = list.filter((x): x is string => typeof x === 'string' && x.trim().length > 0);
      this.form.patchValue({
        organizer: (activity as any)?.organizer ?? '',
        external_partner:
          (activity as any)?.external_partner_name ??
          (activity as any)?.external_partner ??
          '',
      }, { emitEvent: false });
      this.cdr.markForCheck();
    });
  }

  isObjectiveCompleted(objective: string): boolean {
    return this.completedObjectives.has(objective);
  }

  toggleCompletedObjective(objective: string): void {
    if (this.completedObjectives.has(objective)) this.completedObjectives.delete(objective);
    else this.completedObjectives.add(objective);
    this.cdr.markForCheck();
  }

  onFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.fileTouched = true;
    if (input.files?.length) {
      this.selectedFiles.push(...Array.from(input.files));
      input.value = '';
      this.cdr.markForCheck();
    }
  }

  removeFile(index: number): void {
    this.selectedFiles.splice(index, 1);
    this.cdr.markForCheck();
  }

  private uploadFiles(siteId: string, activityId: string): void {
    if (!this.selectedFiles.length) return;
    this.selectedFiles.forEach((file) => {
      const form = new FormData();
      form.append('file', file);
      form.append('site_id', siteId);
      form.append('entity_type', 'ACTIVITY');
      form.append('entity_id', activityId);
      this.documentsApi.upload(form).subscribe({ next: () => {}, error: () => {} });
    });
    this.selectedFiles = [];
    this.cdr.markForCheck();
  }

  close(): void {
    this.closed.emit();
  }

  submit(): void {
    this.submitError = '';
    this.fileTouched = true;
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    if (this.plannedObjectives.length > 0 && this.completedObjectives.size === 0) {
      this.submitError = 'Select at least one completed objective.';
      this.cdr.markForCheck();
      return;
    }
    if (this.selectedFiles.length === 0) {
      this.submitError = 'Please attach at least one file.';
      this.cdr.markForCheck();
      return;
    }
    this.loading = true;
    this.cdr.markForCheck();
    const raw = this.form.getRawValue();
    const payload: CreateRealizedCsrPayload = {
      activity_id: raw.activity_id,
      realized_budget: raw.realized_budget != null && raw.realized_budget !== '' ? Number(raw.realized_budget) : null,
      participants: raw.participants != null && raw.participants !== '' ? Number(raw.participants) : null,
      action_impact_actual: raw.action_impact_actual != null && raw.action_impact_actual !== '' ? Number(raw.action_impact_actual) : null,
      action_impact_unit: raw.action_impact_unit?.trim() || null,
      realization_date: raw.realization_date?.trim() ? raw.realization_date.substring(0, 10) : null,
      comment: raw.comment?.trim() || null,
      completed_objectives: Array.from(this.completedObjectives),
      corporate_image_improved: raw.corporate_image_improved,
      incidents_number: raw.incidents_number != null && raw.incidents_number !== '' ? Number(raw.incidents_number) : null,
      employees_actual: raw.participants != null && raw.participants !== '' ? Number(raw.participants) : null,
      contact_department: raw.contact_department?.trim() || null,
      contact_name: raw.contact_name?.trim() || null,
      contact_email: raw.contact_email?.trim() || null,
    };
    this.realizedApi.create(payload).pipe(
      finalize(() => {
        this.loading = false;
        this.cdr.markForCheck();
      }),
    ).subscribe({
      next: () => {
        const siteId = this.selectedPlan?.site_id;
        const activityId = raw.activity_id;
        if (siteId && activityId && this.selectedFiles.length) {
          this.uploadFiles(siteId, activityId);
        } else {
          this.selectedFiles = [];
        }
        this.created.emit();
        this.closed.emit();
      },
      error: () => {},
    });
  }
}
