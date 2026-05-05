import { Component, inject, OnInit, Input, Output, EventEmitter, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { TranslateModule } from '@ngx-translate/core';
import { catchError, finalize, of, switchMap, timeout } from 'rxjs';
import { CsrPlansApi } from '@features/csr-plan-management/api/csr-plans-api';
import { CsrActivitiesApi } from '../api/csr-activities-api';
import { CategoriesApi, CATEGORY_OTHER_VALUE } from '@features/realized-activity-management/api/categories-api';
import type { CsrPlan } from '@features/csr-plan-management/models/csr-plan.model';
import type { Category } from '@features/realized-activity-management/api/categories-api';

const LOAD_TIMEOUT_MS = 8000;

@Component({
  selector: 'app-planned-activity-create-sidebar',
  standalone: true,
  imports: [ReactiveFormsModule, CommonModule, TranslateModule],
  templateUrl: './planned-activity-create-sidebar.html',
  host: { class: 'flex flex-col flex-1 min-h-0 overflow-hidden' },
})
export class PlannedActivityCreateSidebarComponent implements OnInit {
  private fb = inject(FormBuilder);
  private cdr = inject(ChangeDetectorRef);
  private plansApi = inject(CsrPlansApi);
  private activitiesApi = inject(CsrActivitiesApi);
  private categoriesApi = inject(CategoriesApi);

  @Input() initialPlanId: string | null = null;
  /** Année du plan (depuis la fiche plan) : permet d’afficher « plan réalisé » avant chargement de la liste. */
  @Input() contextPlanYear: number | null = null;
  /** Plan validé en période unlock : libellés indiquant une modification du plan (pas une activité hors plan). */
  @Input() planAmendmentMode = false;

  @Output() closed = new EventEmitter<void>();
  @Output() created = new EventEmitter<void>();

  form!: FormGroup;
  plan: CsrPlan | null = null;
  plansForSelection: CsrPlan[] = [];
  categories: Category[] = [];
  plannedObjectives: string[] = [];
  externalPartners: string[] = [];
  currentYear = new Date().getFullYear();
  loading = false;
  loadingData = true;
  readonly categoryOtherValue = CATEGORY_OTHER_VALUE;

  /** Plan d’une année civile passée (ex. Tianjin 2025 en 2026) → titres « réalisé », pas « planifié ». */
  get isRealizedYearPlan(): boolean {
    const y = this.contextPlanYear ?? this.plan?.year;
    return y != null && y < this.currentYear;
  }

  /** Clé i18n du titre du panneau. */
  createSidebarTitleKey(): string {
    if (this.isRealizedYearPlan) {
      return this.planAmendmentMode
        ? 'PLANNED_ACTIVITY_CREATE.REALIZED_YEAR_AMENDMENT_TITLE'
        : 'PLANNED_ACTIVITY_CREATE.REALIZED_YEAR_DRAFT_TITLE';
    }
    return this.planAmendmentMode
      ? 'PLANNED_ACTIVITY_CREATE.AMENDMENT_TITLE'
      : 'BREADCRUMB.PLANNED_ACTIVITY';
  }

  ngOnInit(): void {
    this.form = this.fb.group({
      plan_id: ['', Validators.required],
      category_id: ['', Validators.required],
      new_category_name: [''],
      activity_number: ['', Validators.required],
      title: ['', Validators.required],
      organization: [''],
      contract_type: [''],
      description: [''],
      collaboration_nature: [''],
      periodicity: [''],
      planned_budget: [null as number | null],
      action_impact_target: [null as number | null],
      action_impact_unit: [''],
      action_impact_duration: [''],
      employees_planned: [null as number | null],
      start_year: [this.currentYear as number | null],
      edition: [null as number | null],
      organizer: [''],
      external_partner: [''],
    });

    this.form.get('plan_id')?.valueChanges.subscribe((id) => this.onPlanSelected(id));
    this.form.get('category_id')?.valueChanges.subscribe(() => this.updateNewCategoryValidators());

    if (this.initialPlanId) {
      this.form.patchValue({ plan_id: this.initialPlanId });
    }

    this.plansApi.list().pipe(
      timeout(LOAD_TIMEOUT_MS),
      catchError(() => of([] as CsrPlan[])),
    ).subscribe({
      next: (list) => {
        const editableStatuses = ['DRAFT', 'REJECTED', 'VALIDATED'];
        let plans = (list || [])
          .filter((p) => (p.year >= this.currentYear || p.id === this.initialPlanId) && editableStatuses.includes(p.status ?? ''))
          .sort((a, b) => b.year - a.year || (a.site_name ?? '').localeCompare(b.site_name ?? ''));
        // If opened from plan detail, ensure the current plan is in the list (e.g. draft for past year)
        if (this.initialPlanId && !plans.some((x) => x.id === this.initialPlanId)) {
          const initial = (list || []).find((x) => x.id === this.initialPlanId);
          if (initial && editableStatuses.includes(initial.status ?? '')) {
            plans = [initial, ...plans];
          }
        }
        this.plansForSelection = plans;
        if (this.initialPlanId) {
          const p = this.plansForSelection.find((x) => x.id === this.initialPlanId);
          if (p) {
            this.plan = p;
            this.form.patchValue({ plan_id: this.initialPlanId }, { emitEvent: false });
          }
        }
        this.loadCategories();
      },
      error: () => {
        this.loadingData = false;
        this.cdr.markForCheck();
      },
    });
  }

  private loadCategories(): void {
    this.categoriesApi.list().pipe(
      timeout(LOAD_TIMEOUT_MS),
      catchError(() => of([] as Category[])),
    ).subscribe({
      next: (cats) => {
        this.categories = Array.isArray(cats) ? cats : [];
        this.loadingData = false;
        this.updateNewCategoryValidators();
        this.cdr.markForCheck();
      },
      error: () => {
        this.loadingData = false;
        this.cdr.markForCheck();
      },
    });
  }

  onPlanSelected(planId: string): void {
    if (!planId) {
      this.plan = null;
      this.cdr.markForCheck();
      return;
    }
    const p = this.plansForSelection.find((x) => x.id === planId) ?? null;
    this.plan = p;
    // Keep start_year aligned with the selected plan year.
    const ctrl = this.form.get('start_year');
    if (ctrl) {
      const y = this.plan?.year ?? this.currentYear;
      ctrl.setValue(y);
    }
    this.cdr.markForCheck();
  }

  isOtherCategorySelected(): boolean {
    return this.form.get('category_id')?.value === CATEGORY_OTHER_VALUE;
  }

  private updateNewCategoryValidators(): void {
    const ctrl = this.form.get('new_category_name');
    if (this.isOtherCategorySelected()) {
      ctrl?.setValidators([Validators.required, Validators.minLength(2)]);
    } else {
      ctrl?.clearValidators();
      ctrl?.setValue('');
    }
    ctrl?.updateValueAndValidity();
  }

  addPlannedObjective(value: string): void {
    const raw = String(value ?? '').trim();
    if (!raw) return;
    if (!this.plannedObjectives.some((o) => o.toLowerCase() === raw.toLowerCase())) {
      this.plannedObjectives.push(raw);
      this.cdr.markForCheck();
    }
  }

  removePlannedObjective(index: number): void {
    this.plannedObjectives.splice(index, 1);
    this.cdr.markForCheck();
  }

  addExternalPartner(value: string): void {
    const raw = String(value ?? '').trim();
    if (!raw) return;
    if (!this.externalPartners.some((p) => p.toLowerCase() === raw.toLowerCase())) {
      this.externalPartners.push(raw);
      this.cdr.markForCheck();
    }
  }

  removeExternalPartner(index: number): void {
    this.externalPartners.splice(index, 1);
    this.cdr.markForCheck();
  }

  close(): void {
    this.closed.emit();
  }

  submit(): void {
    if (this.loading || this.form.invalid || !this.plan) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) return;

    this.loading = true;
    this.cdr.markForCheck();
    const raw = this.form.getRawValue();
    this.addExternalPartner(raw.external_partner);
    this.form.patchValue({ external_partner: '' }, { emitEvent: false });
    const plannedBudget = raw.planned_budget != null && raw.planned_budget !== '' ? Number(raw.planned_budget) : null;

    const categoryId$ = raw.category_id === CATEGORY_OTHER_VALUE && raw.new_category_name?.trim()
      ? this.categoriesApi.create(raw.new_category_name.trim()).pipe(switchMap((cat) => of(cat.id)))
      : of(raw.category_id);

    categoryId$.pipe(
      switchMap((categoryId) =>
        this.activitiesApi.create({
          plan_id: this.plan!.id,
          category_id: categoryId,
          activity_number: raw.activity_number.trim(),
          title: raw.title.trim(),
          organization: raw.organization?.trim() || null,
          contract_type: raw.contract_type?.trim() || null,
          description: raw.description?.trim() || null,
          collaboration_nature: raw.collaboration_nature?.trim() || null,
          periodicity: raw.periodicity?.trim() || null,
          planned_budget: plannedBudget,
          action_impact_target: raw.action_impact_target != null && raw.action_impact_target !== '' ? Number(raw.action_impact_target) : null,
          action_impact_unit: raw.action_impact_unit?.trim() || null,
          action_impact_duration: raw.action_impact_duration?.trim() || null,
          employees_planned: raw.employees_planned != null && raw.employees_planned !== '' ? Number(raw.employees_planned) : null,
          planned_objectives: [...this.plannedObjectives],
          start_year: raw.start_year != null && raw.start_year !== '' ? Number(raw.start_year) : null,
          edition: raw.edition != null && raw.edition !== '' ? Number(raw.edition) : null,
          organizer: raw.organizer?.trim() || null,
          external_partner: this.externalPartners.length ? this.externalPartners.join(', ') : (raw.external_partner?.trim() || null),
          external_partners: this.externalPartners.length ? [...this.externalPartners] : undefined,
        })
      ),
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
