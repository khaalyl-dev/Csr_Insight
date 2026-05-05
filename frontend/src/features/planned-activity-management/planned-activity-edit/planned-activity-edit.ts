import { Component, inject, OnInit, OnDestroy, ChangeDetectorRef, Input, Output, EventEmitter, HostBinding } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { catchError, of, switchMap, timeout } from 'rxjs';
import { CsrActivitiesApi, type PlannedActivityListItem } from '../api/csr-activities-api';
import { CategoriesApi, CATEGORY_OTHER_VALUE } from '@features/realized-activity-management/api/categories-api';
import { RealizedCsrApi } from '@features/realized-activity-management/api/realized-csr-api';
import { HttpClient } from '@angular/common/http';
import { DocumentsApi } from '@features/file-management/api/documents-api';
import type { Document } from '@features/file-management/models/document.model';
import type { Category } from '@features/realized-activity-management/api/categories-api';
import type { RealizedCsr } from '@features/realized-activity-management/models/realized-csr.model';

const MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
const MONTH_LABELS: Record<number, string> = {
  1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
  7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
};

@Component({
  selector: 'app-planned-activity-edit',
  standalone: true,
  imports: [ReactiveFormsModule, CommonModule, RouterLink, TranslateModule],
  templateUrl: './planned-activity-edit.html',
})
export class PlannedActivityEditComponent implements OnInit, OnDestroy {
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private cdr = inject(ChangeDetectorRef);
  private activitiesApi = inject(CsrActivitiesApi);
  private categoriesApi = inject(CategoriesApi);
  private realizedApi = inject(RealizedCsrApi);
  private documentsApi = inject(DocumentsApi);
  private http = inject(HttpClient);
  private location = inject(Location);
  private translate = inject(TranslateService);

  @Input() activityId: string | null = null;
  @Input() planId: string | null = null;
  @Input() planYearParam: number | null = null;
  @Input() sidebarMode = false;
  @Output() closed = new EventEmitter<void>();
  @Output() updated = new EventEmitter<void>();

  @HostBinding('class')
  get hostClass(): string {
    return this.sidebarMode
      ? 'flex flex-col flex-1 min-h-0 min-w-0 h-full overflow-hidden'
      : 'block';
  }

  form!: FormGroup;
  /** Photos linked to this activity. */
  activityPhotos: Document[] = [];
  /** Blob URLs for image thumbnails (auth). */
  photoBlobUrls: Record<string, string> = {};
  private blobUrlsToRevoke: string[] = [];
  uploadingPhotos = false;
  /** When isPlanRealized: form for first realization (or new). */
  realizedForm!: FormGroup;
  activity = null as PlannedActivityListItem | null;
  /** First realization for this activity when isPlanRealized (null if none yet). */
  firstRealization: RealizedCsr | null = null;
  categories: Category[] = [];
  loading = false;
  loadingData = true;
  errorMsg = '';
  readonly categoryOtherValue = CATEGORY_OTHER_VALUE;
  readonly months = MONTHS;
  monthLabel = (m: number) => MONTH_LABELS[m] ?? String(m);
  currentYear = new Date().getFullYear();
  /** Year from query param (when coming from plan detail) or from loaded activity. */
  planYear: number | null = null;

  /** True when the activity belongs to a past-year (realized) plan. */
  get isPlanRealized(): boolean {
    const y = this.planYear ?? this.activity?.year;
    return y != null && y < this.currentYear;
  }

  /** Planned activity edit is restricted to planned_activity table fields only. */
  get showRichRealizedSection(): boolean {
    return false;
  }

  get planRealizationDateMin(): string {
    const y = this.planYear ?? this.activity?.year ?? this.currentYear;
    return `${y}-01-01`;
  }

  get planRealizationDateMax(): string {
    const y = this.planYear ?? this.activity?.year ?? this.currentYear;
    return `${y}-12-31`;
  }

  get pageTitle(): string {
    const key = this.isPlanRealized ? 'PLANNED_ACTIVITY_EDIT.PAGE_TITLE_REALIZED' : 'PLANNED_ACTIVITY_EDIT.PAGE_TITLE_PLANNED';
    return this.translate.instant(key);
  }

  ngOnInit(): void {
    this.form = this.fb.group({
      category_id: ['', Validators.required],
      new_category_name: [''],
      activity_number: ['', Validators.required],
      title: ['', Validators.required],
      description: [''],
      planned_budget: [null as number | null],
      collaboration_nature: [''],
      periodicity: [''],
      action_impact_target: [null as number | null],
      action_impact_unit: [''],
      action_impact_duration: [''],
      organizer: [''],
      start_year: [null as number | null],
      edition: [null as number | null],
      number_external_partners: [null as number | null],
      external_partner: [''],
    });
    this.realizedForm = this.fb.group({
      year: [this.planYear ?? new Date().getFullYear(), [Validators.required, Validators.min(2000), Validators.max(2100)]],
      month: [1, [Validators.required, Validators.min(1), Validators.max(12)]],
      realized_budget: [null as number | null],
      participants: [null as number | null],
      total_hc: [null as number | null],
      percentage_employees: [null as number | null],
      action_impact_actual: [null as number | null],
      action_impact_unit: [''],
      organizer: [''],
      number_external_partners: [null as number | null],
      realization_date: [''],
      comment: [''],
      contact_name: [''],
      contact_email: [''],
      contact_department: [''],
    });

    const id = this.activityId ?? this.route.snapshot.paramMap.get('id');
    const yearParam = this.planYearParam ?? (this.route.snapshot.queryParamMap.get('year') ? parseInt(this.route.snapshot.queryParamMap.get('year')!, 10) : null);
    if (yearParam != null && !isNaN(yearParam)) this.planYear = yearParam;
    if (!id) {
      if (!this.sidebarMode) this.router.navigate(['/planned-activities']);
      return;
    }

    this.loadActivity(id);
  }

  private loadActivity(id: string): void {
    this.activitiesApi.get(id).pipe(
      timeout(8000),
      catchError(() => of(null)),
    ).subscribe({
      next: (a) => {
        this.activity = a;
        if (a?.year != null) this.planYear = a.year;
        if (!a) {
          this.errorMsg = 'Activité introuvable.';
          this.loadingData = false;
          this.cdr.markForCheck();
          return;
        }
        if ((a as PlannedActivityListItem).plan_editable === false) {
          if (this.sidebarMode) this.closed.emit();
          else this.router.navigate(['/planned-activity', a.id], { queryParams: { locked: '1' } });
          return;
        }
        this.form.patchValue({
          category_id: a.category_id ?? '',
          activity_number: a.activity_number ?? '',
          title: a.title ?? '',
          description: a.description ?? '',
          planned_budget: a.is_off_plan ? null : (a.planned_budget ?? null),
          collaboration_nature: a.collaboration_nature ?? '',
          periodicity: (a as any).periodicity ?? '',
          action_impact_target: (a as any).action_impact_target ?? null,
          action_impact_unit: (a as any).action_impact_unit ?? '',
          action_impact_duration: (a as any).action_impact_duration ?? '',
          organizer: (a as any).organizer ?? '',
          start_year: a.start_year ?? null,
          edition: a.edition ?? null,
          number_external_partners: (a as any).number_external_partners ?? null,
          external_partner: a.external_partner_name ?? '',
        });
        this.loadCategories();
        // Realized activity data is edited in realized screens; planned activity edit stays planned-only.
        this.loadActivityPhotos(a.id);
      },
      error: () => {
        this.errorMsg = 'Impossible de charger l\'activité.';
        this.loadingData = false;
        this.cdr.markForCheck();
      },
    });
  }

  // Realized loading/validators removed (year/month fields dropped from realized table).

  private loadActivityPhotos(activityId: string): void {
    this.documentsApi.listByEntity('ACTIVITY', activityId).pipe(
      catchError(() => of([] as Document[])),
    ).subscribe({
      next: (list) => {
        this.activityPhotos = list ?? [];
        this.activityPhotos.filter((d) => this.isImageType(d)).forEach((doc) => {
          const url = this.documentsApi.getServeUrl(doc.file_path);
          this.http.get(url, { responseType: 'blob' }).subscribe({
            next: (blob) => {
              const blobUrl = URL.createObjectURL(blob);
              this.blobUrlsToRevoke.push(blobUrl);
              this.photoBlobUrls = { ...this.photoBlobUrls, [doc.id]: blobUrl };
              this.cdr.markForCheck();
            },
          });
        });
        this.cdr.markForCheck();
      },
    });
  }

  onPhotoFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = input.files;
    if (!files?.length || !this.activity?.id) return;
    const siteId = (this.activity as PlannedActivityListItem).site_id;
    if (!siteId) return;
    this.uploadingPhotos = true;
    this.cdr.markForCheck();
    let done = 0;
    const total = files.length;
    Array.from(files).forEach((file) => {
      const form = new FormData();
      form.append('file', file);
      form.append('site_id', siteId);
      form.append('entity_type', 'ACTIVITY');
      form.append('entity_id', this.activity!.id);
      this.documentsApi.upload(form).subscribe({
        next: (doc) => {
          this.activityPhotos = [...this.activityPhotos, doc];
          done++;
          if (done === total) {
            this.uploadingPhotos = false;
            this.cdr.markForCheck();
          }
        },
        error: () => {
          done++;
          if (done === total) {
            this.uploadingPhotos = false;
            this.cdr.markForCheck();
          }
        },
      });
    });
    input.value = '';
  }

  deletePhoto(doc: Document): void {
    this.documentsApi.deleteDocument(doc.id).subscribe({
      next: () => {
        this.activityPhotos = this.activityPhotos.filter((d) => d.id !== doc.id);
        this.cdr.markForCheck();
      },
    });
  }

  isImageType(doc: Document): boolean {
    const t = (doc.file_type || '').toLowerCase();
    return ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(t);
  }

  getPhotoUrl(doc: Document): string {
    return this.photoBlobUrls[doc.id] ?? this.documentsApi.getServeUrl(doc.file_path);
  }

  getDownloadUrl(doc: Document): string {
    return this.documentsApi.getDownloadUrl(doc.file_path);
  }

  private loadCategories(): void {
    this.categoriesApi.list().pipe(
      timeout(8000),
      catchError(() => of([] as Category[])),
    ).subscribe({
      next: (cats) => {
        this.categories = Array.isArray(cats) ? cats : [];
        this.loadingData = false;
        this.form.get('category_id')?.valueChanges.subscribe(() => this.updateNewCategoryValidators());
        this.updateNewCategoryValidators();
        this.cdr.markForCheck();
      },
      error: () => {
        this.loadingData = false;
        this.errorMsg = 'Impossible de charger les catégories.';
        this.cdr.markForCheck();
      },
    });
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
    this.cdr.markForCheck();
  }

  submit(): void {
    if (!this.activity || this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    if (this.showRichRealizedSection && this.realizedForm.invalid) {
      this.realizedForm.markAllAsTouched();
      return;
    }
    const raw = this.form.getRawValue();
    const plannedBudget =
      this.activity.is_off_plan
        ? null
        : raw.planned_budget != null && raw.planned_budget !== ''
          ? Number(raw.planned_budget)
          : null;
    const r = this.realizedForm.getRawValue();
    const organizerForActivity = raw.organizer?.trim() || null;

    const categoryId$ = raw.category_id === CATEGORY_OTHER_VALUE && raw.new_category_name?.trim()
      ? this.categoriesApi.create(raw.new_category_name.trim()).pipe(switchMap((cat) => of(cat.id)))
      : of(raw.category_id);

    this.loading = true;
    this.errorMsg = '';
    categoryId$.pipe(
      switchMap((categoryId) =>
        this.activitiesApi.update(this.activity!.id, {
          category_id: categoryId,
          activity_number: raw.activity_number.trim(),
          title: raw.title.trim(),
          description: raw.description?.trim() || null,
          planned_budget: plannedBudget,
          collaboration_nature: raw.collaboration_nature?.trim() || null,
          periodicity: raw.periodicity?.trim() || null,
          action_impact_target: raw.action_impact_target != null && raw.action_impact_target !== '' ? Number(raw.action_impact_target) : null,
          action_impact_unit: raw.action_impact_unit?.trim() || null,
          action_impact_duration: raw.action_impact_duration?.trim() || null,
          organizer: organizerForActivity,
          edition: raw.edition != null && raw.edition !== '' ? Number(raw.edition) : null,
          start_year: raw.start_year != null && raw.start_year !== '' ? Number(raw.start_year) : null,
          external_partner: raw.external_partner?.trim() || null,
          number_external_partners: raw.number_external_partners != null && raw.number_external_partners !== '' ? Number(raw.number_external_partners) : null,
        })
      ),
      switchMap(() => {
        if (!this.showRichRealizedSection) return of(null);
        const planY = this.planYear ?? this.activity!.year;
        let year: number;
        let month: number;
        if (this.activity!.is_off_plan && planY != null) {
          year = planY;
          const rd = r.realization_date?.trim();
          if (rd && rd.length >= 10) {
            const d = new Date(`${rd.slice(0, 10)}T12:00:00`);
            month = !Number.isNaN(d.getTime()) ? d.getMonth() + 1 : Number(r.month) || 1;
          } else {
            month = Number(r.month) || 1;
          }
        } else {
          year = Number(r.year);
          month = Number(r.month);
        }
        const realizationDateStr = r.realization_date?.trim() ? r.realization_date.trim().slice(0, 10) : null;
        const payload = {
          year,
          month,
          realized_budget: r.realized_budget != null && r.realized_budget !== '' ? Number(r.realized_budget) : null,
          participants: r.participants != null && r.participants !== '' ? Number(r.participants) : null,
          percentage_employees:
            r.percentage_employees != null && r.percentage_employees !== '' ? Number(r.percentage_employees) : null,
          action_impact_actual: r.action_impact_actual != null && r.action_impact_actual !== '' ? Number(r.action_impact_actual) : null,
          action_impact_unit: r.action_impact_unit?.trim() || null,
          organizer: r.organizer?.trim() || null,
          number_external_partners:
            r.number_external_partners != null && r.number_external_partners !== ''
              ? Number(r.number_external_partners)
              : null,
          realization_date: realizationDateStr,
          comment: r.comment?.trim() || null,
          contact_name: r.contact_name?.trim() || null,
          contact_email: r.contact_email?.trim() || null,
          contact_department: r.contact_department?.trim() || null,
        };
        if (this.firstRealization) {
          return this.realizedApi.update(this.firstRealization.id, payload).pipe(switchMap(() => of(null)));
        }
        return this.realizedApi.create({ activity_id: this.activity!.id, ...payload }).pipe(switchMap(() => of(null)));
      }),
    ).subscribe({
      next: () => {
        this.loading = false;
        if (this.sidebarMode) {
          this.updated.emit();
          this.closed.emit();
        } else if (this.activity?.plan_id) {
          this.router.navigate(['/csr-plans', this.activity.plan_id]);
        } else {
          this.router.navigate(['/planned-activities']);
        }
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.loading = false;
        this.errorMsg = err.error?.message ?? 'Erreur lors de l\'enregistrement.';
        this.cdr.markForCheck();
      },
    });
  }

  cancel(): void {
    if (this.sidebarMode) this.closed.emit();
    else this.location.back();
  }

  ngOnDestroy(): void {
    this.blobUrlsToRevoke.forEach((u) => URL.revokeObjectURL(u));
  }
}
