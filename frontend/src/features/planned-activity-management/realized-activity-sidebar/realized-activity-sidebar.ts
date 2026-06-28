import { Component, inject, Input, Output, EventEmitter, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslateModule } from '@ngx-translate/core';
import { catchError, finalize, of, switchMap, timeout } from 'rxjs';
import { CsrActivitiesApi, type OffPlanRealizationPayload } from '../api/csr-activities-api';
import { DocumentsApi } from '@features/file-management/api/documents-api';
import { CategoriesApi, CATEGORY_OTHER_VALUE } from '@features/realized-activity-management/api/categories-api';
import type { Category } from '@features/realized-activity-management/api/categories-api';
import { AuthStore } from '@core/services/auth-store';

const LOAD_TIMEOUT_MS = 8000;

@Component({
  selector: 'app-realized-activity-sidebar',
  standalone: true,
  imports: [ReactiveFormsModule, CommonModule, TranslateModule],
  templateUrl: './realized-activity-sidebar.html',
  host: {
    class: 'flex flex-col flex-1 min-h-0 overflow-hidden block w-full',
  },
})
export class RealizedActivitySidebarComponent implements OnInit {
  private fb = inject(FormBuilder);
  private cdr = inject(ChangeDetectorRef);
  private activitiesApi = inject(CsrActivitiesApi);
  private documentsApi = inject(DocumentsApi);
  private categoriesApi = inject(CategoriesApi);
  private authStore = inject(AuthStore);

  @Input({ required: true }) planId!: string;
  @Input() siteLabel = '';
  @Input() planYear: number | null = null;
  @Input() submissionMode: 'off_plan' | 'plan_realized_draft' = 'plan_realized_draft';
  @Input() titleTranslateKey = 'OFF_PLAN_SIDEBAR.TITLE';
  @Input() hintTranslateKey: string | null = null;

  @Output() closed = new EventEmitter<void>();
  @Output() created = new EventEmitter<void>();

  form!: FormGroup;
  loading = false;
  submitError: string | null = null;
  selectedFiles: File[] = [];
  externalPartners: string[] = [];
  plannedObjectives: string[] = [];
  completedObjectives = new Set<string>();
  currentYear = new Date().getFullYear();

  readonly categoryOtherValue = CATEGORY_OTHER_VALUE;
  categories: Category[] = [];
  loadingCategories = true;

  get planRealizationDateMin(): string {
    const y = this.planYear ?? this.currentYear;
    return `${y}-01-01`;
  }

  get planRealizationDateMax(): string {
    const y = this.planYear ?? this.currentYear;
    return `${y}-12-31`;
  }

  get isOffPlanSubmission(): boolean {
    return this.submissionMode === 'off_plan';
  }

  get shouldRequirePlanningFields(): boolean {
    // In plan_realized_draft flow, backend still expects planning metadata even if off-plan is selected.
    return this.submissionMode === 'plan_realized_draft' || !this.isOffPlanSelected();
  }

  isCorporateUser(): boolean {
    return this.authStore.userRole() === 'corporate';
  }

  ngOnInit(): void {
    this.form = this.fb.group({
      activity_number: ['', [Validators.required, Validators.maxLength(50)]],
      title: ['', [Validators.required, Validators.maxLength(255)]],
      is_off_plan: ['NO', Validators.required],
      organization: ['', Validators.required],
      contract_type: ['', Validators.required],
      description: ['', Validators.required],

      category_id: ['', Validators.required],
      new_category_name: [''],
      collaboration_nature: [''],
      periodicity: [''],
      consumed_budget: [null as number | null],
      action_impact_target: [null as number | null],
      action_impact_unit: [''],
      action_impact_duration: [''],
      employees_planned: [null as number | null],
      start_year: [this.planYear ?? this.currentYear],
      edition: [null as number | null],

      employees_actual: [null as number | null, Validators.required],
      realized_budget: [null as number | null, Validators.required],
      action_impact_actual: [null as number | null, Validators.required],
      action_impact_unit_realized: ['', Validators.required],

      organizer: ['', Validators.required],
      external_partner: [''],
      realization_date: ['', Validators.required],

      validation_mode: ['101' as '101' | '111', Validators.required],

      comment: ['', Validators.required],
      corporate_image_improved: [null as boolean | null, Validators.required],
      incidents_number: [null as number | null, Validators.required],
      contact_name: ['', Validators.required],
      contact_email: ['', [Validators.required, Validators.email]],
      contact_department: ['', Validators.required],
    });

    this.form.get('category_id')?.valueChanges.subscribe(() => this.updateNewCategoryValidators());
    this.form.get('is_off_plan')?.valueChanges.subscribe(() => this.updatePlanningSectionValidators());
    this.updatePlanningSectionValidators();
    if (this.submissionMode === 'plan_realized_draft') {
      this.applyPlanRealizedDraftRequiredValidators();
      this.form.get('validation_mode')?.clearValidators();
      this.form.get('validation_mode')?.updateValueAndValidity({ emitEvent: false });
    }
    if (this.isCorporateUser()) {
      const v = this.form.get('validation_mode');
      v?.setValue('101', { emitEvent: false });
      v?.disable({ emitEvent: false });
      v?.clearValidators();
      v?.updateValueAndValidity({ emitEvent: false });
    }
    this.loadCategories();
  }

  isOffPlanSelected(): boolean {
    return this.form.get('is_off_plan')?.value === 'YES';
  }

  private updatePlanningSectionValidators(): void {
    const planningFields = [
      'collaboration_nature',
      'periodicity',
      'consumed_budget',
      'action_impact_target',
      'action_impact_unit',
      'action_impact_duration',
      'start_year',
      'edition',
    ];
    const required = this.shouldRequirePlanningFields;
    for (const field of planningFields) {
      const ctrl = this.form.get(field);
      if (!ctrl) continue;
      ctrl.setValidators(required ? [Validators.required] : []);
      if (!required) ctrl.setValue(null, { emitEvent: false });
      ctrl.updateValueAndValidity({ emitEvent: false });
    }
    // When marked off-plan, these planning metrics must be blocked and defaulted.
    const blockedWhenOffPlan = ['consumed_budget', 'action_impact_target', 'action_impact_unit', 'employees_planned'];
    for (const field of blockedWhenOffPlan) {
      const ctrl = this.form.get(field);
      if (!ctrl) continue;
      if (this.isOffPlanSelected()) {
        if (field === 'action_impact_unit') ctrl.setValue(null, { emitEvent: false });
        else ctrl.setValue(0, { emitEvent: false });
        ctrl.disable({ emitEvent: false });
      } else {
        ctrl.enable({ emitEvent: false });
      }
      ctrl.updateValueAndValidity({ emitEvent: false });
    }
    if (this.submissionMode === 'plan_realized_draft') {
      this.applyPlanRealizedDraftRequiredValidators();
    }
  }

  private loadCategories(): void {
    this.categoriesApi
      .list()
      .pipe(timeout(LOAD_TIMEOUT_MS), catchError(() => of([] as Category[])))
      .subscribe({
        next: (cats) => {
          this.categories = Array.isArray(cats) ? cats : [];
          this.loadingCategories = false;
          this.updateNewCategoryValidators();
          this.cdr.markForCheck();
        },
        error: () => {
          this.loadingCategories = false;
          this.cdr.markForCheck();
        },
      });
  }

  isOtherCategorySelected(): boolean {
    return this.form.get('category_id')?.value === this.categoryOtherValue;
  }

  private updateNewCategoryValidators(): void {
    const ctrl = this.form.get('new_category_name');
    if (!ctrl) return;
    if (this.isOtherCategorySelected()) ctrl.setValidators([Validators.required, Validators.minLength(2)]);
    else {
      ctrl.clearValidators();
      ctrl.setValue('');
    }
    ctrl.updateValueAndValidity();
  }

  close(): void { this.closed.emit(); }

  onFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files?.length) {
      this.selectedFiles.push(...Array.from(input.files));
      input.value = '';
      this.cdr.markForCheck();
    }
  }
  removeFile(index: number): void { this.selectedFiles.splice(index, 1); this.cdr.markForCheck(); }

  addExternalPartnerFromInput(): void {
    const ctrl = this.form.get('external_partner');
    const raw = String(ctrl?.value ?? '').trim();
    if (!raw) return;
    const exists = this.externalPartners.some((p) => p.toLowerCase() === raw.toLowerCase());
    if (!exists) this.externalPartners.push(raw);
    ctrl?.setValue('');
    this.cdr.markForCheck();
  }
  removeExternalPartner(index: number): void { this.externalPartners.splice(index, 1); this.cdr.markForCheck(); }

  addPlannedObjective(value: string): void {
    const raw = String(value ?? '').trim();
    if (!raw) return;
    if (!this.plannedObjectives.some((o) => o.toLowerCase() === raw.toLowerCase())) this.plannedObjectives.push(raw);
    this.cdr.markForCheck();
  }
  removePlannedObjective(index: number): void {
    const removed = this.plannedObjectives[index];
    this.plannedObjectives.splice(index, 1);
    if (removed) this.completedObjectives.delete(removed);
    this.cdr.markForCheck();
  }
  isCompletedObjectiveSelected(objective: string): boolean { return this.completedObjectives.has(objective); }
  toggleCompletedObjective(objective: string): void {
    if (this.completedObjectives.has(objective)) this.completedObjectives.delete(objective);
    else this.completedObjectives.add(objective);
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

  private buildPayload(categoryId: string): OffPlanRealizationPayload {
    const raw = this.form.getRawValue();
    const isOffPlan = this.isOffPlanSelected();
    const includePlannedDetails = this.submissionMode === 'plan_realized_draft' ? true : false;
    const planY = this.planYear ?? this.currentYear;
    let month = new Date().getMonth() + 1;
    const rd = raw.realization_date?.trim();
    if (rd && rd.length >= 10) {
      const d = new Date(`${rd.slice(0, 10)}T12:00:00`);
      if (!Number.isNaN(d.getTime())) month = d.getMonth() + 1;
    }
    return {
      plan_id: this.planId,
      is_off_plan: this.isOffPlanSelected(),
      validation_mode: this.submissionMode === 'plan_realized_draft' ? '101' : raw.validation_mode,
      include_planned_details: includePlannedDetails,
      activity_number: String(raw.activity_number).trim(),
      title: String(raw.title).trim(),
      organization: raw.organization?.trim() || null,
      contract_type: raw.contract_type?.trim() || null,
      description: raw.description?.trim() ? String(raw.description).trim() : null,
      category_id: categoryId,
      collaboration_nature: raw.collaboration_nature?.trim() || null,
      periodicity: includePlannedDetails ? (raw.periodicity?.trim() || null) : null,
      consumed_budget: includePlannedDetails ? (isOffPlan ? 0 : (raw.consumed_budget != null && raw.consumed_budget !== '' ? Number(raw.consumed_budget) : null)) : null,
      action_impact_target: includePlannedDetails ? (isOffPlan ? 0 : (raw.action_impact_target != null && raw.action_impact_target !== '' ? Number(raw.action_impact_target) : null)) : null,
      action_impact_unit: isOffPlan ? null : (raw.action_impact_unit?.trim() || null),
      action_impact_duration: raw.action_impact_duration?.trim() || null,
      employees_planned: isOffPlan ? 0 : (raw.employees_planned != null && raw.employees_planned !== '' ? Number(raw.employees_planned) : null),
      planned_objectives: [...this.plannedObjectives],
      start_year: raw.start_year != null && raw.start_year !== '' ? Number(raw.start_year) : null,
      edition: raw.edition != null && raw.edition !== '' ? Number(raw.edition) : null,
      external_partner: this.externalPartners.length ? this.externalPartners.join(', ') : (raw.external_partner?.trim() || null),
      external_partners: this.externalPartners.length ? [...this.externalPartners] : undefined,
      year: planY,
      month,
      realized_budget: raw.realized_budget != null && raw.realized_budget !== '' ? Number(raw.realized_budget) : null,
      employees_actual: raw.employees_actual != null && raw.employees_actual !== '' ? Number(raw.employees_actual) : null,
      action_impact_actual: raw.action_impact_actual != null && raw.action_impact_actual !== '' ? Number(raw.action_impact_actual) : null,
      action_impact_unit_realized: raw.action_impact_unit_realized?.trim() || null,
      organizer: raw.organizer?.trim() || null,
      realization_date: raw.realization_date?.trim() ? raw.realization_date.substring(0, 10) : null,
      comment: raw.comment?.trim() || null,
      completed_objectives: Array.from(this.completedObjectives),
      corporate_image_improved: !!raw.corporate_image_improved,
      incidents_number: raw.incidents_number != null && raw.incidents_number !== '' ? Number(raw.incidents_number) : null,
      contact_department: raw.contact_department?.trim() || null,
      contact_name: raw.contact_name?.trim() || null,
      contact_email: raw.contact_email?.trim() || null,
    };
  }

  private applyPlanRealizedDraftRequiredValidators(): void {
    const requiredFields = [
      'description','collaboration_nature','periodicity','organization','contract_type','consumed_budget',
      'action_impact_target','action_impact_unit','action_impact_duration','start_year','edition',
      'employees_actual','realized_budget','action_impact_actual','action_impact_unit_realized','organizer',
      'incidents_number','realization_date','comment','contact_name','contact_email','contact_department',
    ];
    const planningFields = new Set([
      'collaboration_nature',
      'consumed_budget',
      'action_impact_target',
      'action_impact_unit',
      'action_impact_duration',
      'start_year',
      'edition',
      'employees_planned',
    ]);
    for (const field of requiredFields) {
      const ctrl = this.form.get(field);
      if (!ctrl) continue;
      if (this.isOffPlanSelected() && planningFields.has(field)) {
        ctrl.clearValidators();
        ctrl.updateValueAndValidity({ emitEvent: false });
        continue;
      }
      if (field === 'contact_email') ctrl.setValidators([Validators.required, Validators.email]);
      else ctrl.setValidators([Validators.required]);
      ctrl.updateValueAndValidity({ emitEvent: false });
    }
  }

  submit(): void {
    this.addExternalPartnerFromInput();
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    if (this.externalPartners.length === 0) { this.submitError = 'Please add at least one external partner.'; this.cdr.markForCheck(); return; }
    if (this.plannedObjectives.length === 0) { this.submitError = 'Please add at least one announced objective.'; this.cdr.markForCheck(); return; }
    if (this.completedObjectives.size === 0) { this.submitError = 'Please select at least one completed objective.'; this.cdr.markForCheck(); return; }
    if (this.selectedFiles.length === 0) { this.submitError = 'Please attach at least one file.'; this.cdr.markForCheck(); return; }
    this.submitError = null;
    this.loading = true;
    this.cdr.markForCheck();
    const raw = this.form.getRawValue();
    const categoryId$ = raw.category_id === this.categoryOtherValue && raw.new_category_name?.trim()
      ? this.categoriesApi.create(raw.new_category_name.trim()).pipe(switchMap((cat) => of(cat.id)))
      : of(raw.category_id);
    const api$ = !this.isOffPlanSubmission
      ? (cid: string) => this.activitiesApi.createPlanRealizedDraftWithRealization(this.buildPayload(cid)).pipe(timeout(LOAD_TIMEOUT_MS))
      : (cid: string) => this.activitiesApi.createOffPlanRealization(this.buildPayload(cid)).pipe(timeout(LOAD_TIMEOUT_MS));
    categoryId$
      .pipe(
        switchMap((categoryId) => api$(categoryId)),
        catchError((err) => {
          const msg = err?.error?.message || err?.message || 'Erreur lors de la soumission';
          this.submitError = String(msg);
          return of(null);
        }),
        finalize(() => { this.loading = false; this.cdr.markForCheck(); }),
      )
      .subscribe({
        next: (res) => {
          if (!res) return;
          const siteId = res.activity.site_id;
          const activityId = res.activity.id;
          if (siteId && activityId && this.selectedFiles.length) this.uploadFiles(siteId, activityId);
          else this.selectedFiles = [];
          this.created.emit();
          this.closed.emit();
        },
      });
  }
}
