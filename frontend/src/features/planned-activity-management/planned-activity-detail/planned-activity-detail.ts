import { Component, inject, OnInit, OnDestroy, signal } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { CsrActivitiesApi, type PlannedActivityListItem } from '../api/csr-activities-api';
import { DocumentsApi } from '@features/file-management/api/documents-api';
import type { Document } from '@features/file-management/models/document.model';
import { BreadcrumbService } from '@core/services/breadcrumb.service';
import { PlannedActivityEditComponent } from '../planned-activity-edit/planned-activity-edit';
import { RealizedCreateSidebarComponent } from '@features/realized-activity-management/realized-create-sidebar/realized-create-sidebar';
import { AuthStore } from '@core/services/auth-store';

@Component({
  selector: 'app-planned-activity-detail',
  standalone: true,
  imports: [CommonModule, RouterModule, TranslateModule, PlannedActivityEditComponent, RealizedCreateSidebarComponent],
  templateUrl: './planned-activity-detail.html',
})
export class PlannedActivityDetailComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private location = inject(Location);
  private api = inject(CsrActivitiesApi);
  private documentsApi = inject(DocumentsApi);
  private http = inject(HttpClient);
  private breadcrumb = inject(BreadcrumbService);
  private translate = inject(TranslateService);
  private authStore = inject(AuthStore);

  activity = signal<PlannedActivityListItem | null>(null);
  photos = signal<Document[]>([]);
  /** Blob URLs for image photos (so img works with auth). */
  photoBlobUrls = signal<Record<string, string>>({});
  loading = signal(true);
  errorMsg = signal('');
  private currentYear = new Date().getFullYear();
  private blobUrls: string[] = [];
  /** Year from query param (when coming from plan detail) or from loaded activity. */
  planYear = signal<number | null>(null);

  /** True when the activity belongs to a past-year (realized) plan. */
  isPlanRealized(): boolean {
    const y = this.planYear() ?? this.activity()?.year;
    return y != null && y < this.currentYear;
  }

  /** Realized data can be submitted only when parent plan is validated. */
  canSubmitRealizedData(): boolean {
    const status = (this.activity()?.plan_status ?? '').toUpperCase();
    return status === 'VALIDATED';
  }

  canManageActivity(): boolean {
    return !this.authStore.isValidatorLevel() && this.activity()?.plan_editable !== false;
  }

  canAddRealization(): boolean {
    const act = this.activity();
    return !!(
      !this.authStore.isValidatorLevel() &&
      act?.plan_id &&
      !this.isPlanRealized() &&
      this.canSubmitRealizedData() &&
      act.plan_editable !== false
    );
  }

  activityTitle(): string {
    return this.activity()?.title || (this.isPlanRealized() ? this.translate.instant('PLANNED_ACTIVITY_DETAIL.TITLE_REALIZED') : this.translate.instant('PLANNED_ACTIVITY_DETAIL.TITLE_PLANNED'));
  }

  sectionTitle(): string {
    return this.isPlanRealized() ? this.translate.instant('PLANNED_ACTIVITY_DETAIL.SECTION_INFO_REALIZED') : this.translate.instant('PLANNED_ACTIVITY_DETAIL.SECTION_INFO_PLANNED');
  }

  /** Activity or plan status token → i18n (shared CSR enums). */
  csrStatusLabel(status: string | null | undefined): string {
    const s = (status || '').toUpperCase();
    const keys: Record<string, string> = {
      DRAFT: 'PLAN_DETAIL.STATUS_DRAFT',
      SUBMITTED: 'PLAN_DETAIL.STATUS_SUBMITTED',
      VALIDATED: 'PLAN_DETAIL.STATUS_VALIDATED',
      REJECTED: 'PLAN_DETAIL.STATUS_REJECTED',
      LOCKED: 'PLAN_DETAIL.STATUS_VALIDATED_LOCKED',
      IN_PROGRESS: 'PLAN_DETAIL.REALIZATION_STATUS_IN_PROGRESS',
      COMPLETED: 'PLAN_DETAIL.REALIZATION_STATUS_COMPLETED',
      PLANNED: 'PLAN_DETAIL.REALIZATION_STATUS_PLANNED',
      UNDER_REVIEW: 'PLAN_DETAIL.ACTIVITY_LIFECYCLE_UNDER_REVIEW',
      CANCELLED: 'PLAN_DETAIL.ACTIVITY_STATUS_CANCELLED',
    };
    const k = keys[s];
    return k ? this.translate.instant(k) : (status || '–');
  }

  validationModeLabel(mode: string | null | undefined): string {
    const m = (mode || '').trim();
    if (m === '111') return this.translate.instant('PLAN_VALIDATION.MODE_ALL');
    if (m === '101') return this.translate.instant('PLAN_VALIDATION.MODE_CORPORATE_ONLY');
    return m || '–';
  }

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    const yearParam = this.route.snapshot.queryParamMap.get('year');
    if (yearParam !== null) {
      const y = parseInt(yearParam, 10);
      if (!isNaN(y)) this.planYear.set(y);
    }
    if (!id) {
      this.router.navigate(['/planned-activities']);
      return;
    }
    this.api.get(id).subscribe({
      next: (data) => {
        this.activity.set(data);
        if (data.year != null) this.planYear.set(data.year);
        this.loading.set(false);
        const siteName = data.site_name ?? data.site_code ?? this.translate.instant('PLANNED_ACTIVITY_DETAIL.ACTIVITY_FALLBACK');
        const title = (data.title ?? '').slice(0, 40) || this.translate.instant('PLANNED_ACTIVITY_DETAIL.TITLE_PLANNED');
        this.breadcrumb.setContext([siteName, String(data.year ?? ''), title]);
        this.documentsApi.listByEntity('ACTIVITY', data.id).subscribe({
          next: (list) => {
            const docs = list ?? [];
            this.photos.set(docs);
            const imageDocs = docs.filter((d) => this.isImageType(d));
            imageDocs.forEach((doc) => {
              const url = this.documentsApi.getServeUrl(doc.file_path);
              this.http.get(url, { responseType: 'blob' }).subscribe({
                next: (blob) => {
                  const blobUrl = URL.createObjectURL(blob);
                  this.blobUrls.push(blobUrl);
                  this.photoBlobUrls.update((m) => ({ ...m, [doc.id]: blobUrl }));
                },
              });
            });
          },
          error: () => {},
        });
      },
      error: (err) => {
        this.loading.set(false);
        this.errorMsg.set(err.error?.message ?? this.translate.instant('PLANNED_ACTIVITY_DETAIL.NOT_FOUND'));
      },
    });
  }

  isImageType(doc: Document): boolean {
    const t = (doc.file_type || '').toLowerCase();
    return ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(t);
  }

  getPhotoUrl(doc: Document): string {
    const urls = this.photoBlobUrls();
    return urls[doc.id] ?? this.documentsApi.getServeUrl(doc.file_path);
  }

  getDownloadUrl(doc: Document): string {
    return this.documentsApi.getDownloadUrl(doc.file_path);
  }

  previewDoc(doc: Document, ev?: Event): void {
    ev?.preventDefault();
    ev?.stopPropagation();
    const url = this.documentsApi.getServeUrl(doc.file_path);
    this.http.get(url, { responseType: 'blob' }).subscribe({
      next: (blob) => {
        const blobUrl = URL.createObjectURL(blob);
        this.blobUrls.push(blobUrl);
        window.open(blobUrl, '_blank', 'noopener');
      },
    });
  }

  back(): void {
    this.location.back();
  }

  showEditSidebar = signal(false);

  openEditSidebar(): void {
    this.showEditSidebar.set(true);
  }

  closeEditSidebar(): void {
    this.showEditSidebar.set(false);
  }

  onActivityUpdated(): void {
    this.closeEditSidebar();
    const act = this.activity();
    if (act?.id) {
      this.api.get(act.id).subscribe({
        next: (data) => this.activity.set(data),
      });
    }
  }

  showAddRealizationSidebar = signal(false);
  showDeleteModal = signal(false);

  openAddRealizationSidebar(): void {
    this.showAddRealizationSidebar.set(true);
  }

  closeAddRealizationSidebar(): void {
    this.showAddRealizationSidebar.set(false);
  }

  onRealizationCreated(): void {
    this.closeAddRealizationSidebar();
    this.router.navigate(['/realized-csr']);
  }

  openDeleteModal(): void {
    this.showDeleteModal.set(true);
  }

  closeDeleteModal(): void {
    this.showDeleteModal.set(false);
  }

  confirmDeleteActivity(): void {
    this.closeDeleteModal();
    this.deleteActivity();
  }

  private deleteActivity(): void {
    const act = this.activity();
    if (!act?.id) return;
    this.api.delete(act.id).subscribe({
      next: () => {
        if (act.plan_id) {
          this.router.navigate(['/csr-plans', act.plan_id]);
          return;
        }
        this.router.navigate(['/planned-activities']);
      },
      error: (err) => {
        this.errorMsg.set(err.error?.message ?? this.translate.instant('PLANNED_ACTIVITY_DETAIL.DELETE_ERROR'));
      },
    });
  }

  ngOnDestroy(): void {
    this.blobUrls.forEach((u) => URL.revokeObjectURL(u));
    this.breadcrumb.clearContext();
  }
}
