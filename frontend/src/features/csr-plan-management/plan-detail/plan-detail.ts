import { ChangeDetectorRef, Component, inject, OnInit, OnDestroy, signal, HostListener } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { CsrPlansApi, CsrPlanDetail, type CsrPlanActivityDetail } from '../api/csr-plans-api';
import { CsrActivitiesApi } from '@features/planned-activity-management/api/csr-activities-api';
import { AuthStore } from '@core/services/auth-store';
import { BreadcrumbService } from '@core/services/breadcrumb.service';
import { PlannedActivityCreateSidebarComponent } from '@features/planned-activity-management/planned-activity-create-sidebar/planned-activity-create-sidebar';
import { PlannedActivityEditComponent } from '@features/planned-activity-management/planned-activity-edit/planned-activity-edit';
import { RealizedActivitySidebarComponent } from '@features/planned-activity-management/realized-activity-sidebar/realized-activity-sidebar';
import { RealizedCreateSidebarComponent } from '@features/realized-activity-management/realized-create-sidebar/realized-create-sidebar';
import { RealizedEditComponent } from '@features/realized-activity-management/realized-edit/realized-edit';
import { RealizedCsrApi } from '@features/realized-activity-management/api/realized-csr-api';
import type { RealizedCsr } from '@features/realized-activity-management/models/realized-csr.model';
import {
  initialFixedContextMenuLeft,
  initialFixedContextMenuTopBelow,
  scheduleFixedContextMenuPosition,
} from '@core/utils/fixed-context-menu';

@Component({
  selector: 'app-plan-detail',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    TranslateModule,
    PlannedActivityCreateSidebarComponent,
    PlannedActivityEditComponent,
    RealizedActivitySidebarComponent,
    RealizedCreateSidebarComponent,
    RealizedEditComponent,
  ],
  templateUrl: './plan-detail.html'
})
export class PlanDetailComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private location = inject(Location);
  private plansApi = inject(CsrPlansApi);
  private activitiesApi = inject(CsrActivitiesApi);
  private realizedApi = inject(RealizedCsrApi);
  private authStore = inject(AuthStore);
  private breadcrumb = inject(BreadcrumbService);
  private translate = inject(TranslateService);
  private cdr = inject(ChangeDetectorRef);

  plan = signal<CsrPlanDetail | null>(null);
  loading = signal(true);
  errorMsg = signal('');
  actionLoading = signal(false);
  currentYear = new Date().getFullYear();

  private isCorporateUser(): boolean {
    const role = (this.authStore.user()?.role ?? '').toLowerCase();
    return role === 'corporate';
  }

  private canCreateActivities(): boolean { return !this.authStore.isValidatorLevel() && this.authStore.hasPermission('activity.create'); }
  private canUpdateActivities(): boolean { return !this.authStore.isValidatorLevel() && this.authStore.hasPermission('activity.update'); }
  private canDeleteActivities(): boolean { return !this.authStore.isValidatorLevel() && this.authStore.hasPermission('activity.delete'); }
  private canSubmitPlan(): boolean { return !this.authStore.isValidatorLevel() && this.authStore.hasPermission('plan.submit'); }
  private canUpdatePlanPermission(): boolean { return !this.authStore.isValidatorLevel() && this.authStore.hasPermission('plan.update'); }
  private canCreateRealizationPermission(): boolean { return !this.authStore.isValidatorLevel() && this.authStore.hasPermission('realized_activity.create'); }

  private planYearValue(): number | null {
    const p = this.plan();
    if (!p) return null;
    const y = Number(p.year);
    return Number.isFinite(y) ? y : null;
  }

  private isPastYearPlan(): boolean {
    const y = this.planYearValue();
    return y != null && y < this.currentYear;
  }

  /** Plan KPIs for past-year plans or plans submitted early as CSR reports. */
  showPlanKpis(): boolean {
    const p = this.plan();
    return this.isPastYearPlan() || !!p?.realization_report_submitted_at;
  }

  /** Plan is "planifié" (current or future year) → show only planned-activity columns. */
  get isPlanPlanned(): boolean {
    const y = this.planYearValue();
    return y != null ? y >= this.currentYear : true;
  }

  /** True when this plan’s year is the current calendar year. */
  isPlanCalendarYearCurrent(): boolean {
    const y = this.planYearValue();
    return y != null && y === this.currentYear;
  }

  /** Submit realization data only for current-year approved plans not yet closed as CSR report. */
  canSubmitRealizationDataOnPlan(): boolean {
    const p = this.plan();
    return (
      this.isPlanCalendarYearCurrent() &&
      p?.status === 'VALIDATED' &&
      !p?.realization_report_submitted_at
    );
  }

  /** Submit entire plan as CSR report (current/future year, approved, locked, partial realization OK). */
  canSubmitPlanForRealization(): boolean {
    const p = this.plan();
    if (!p || !this.canCreateRealizationPermission()) return false;
    if (p.realization_report_submitted_at) return false;
    const y = this.planYearValue();
    if (y == null || y < this.currentYear) return false;
    if (p.status !== 'VALIDATED') return false;
    if (this.isUnlockUntilFuture()) return false;
    return true;
  }

  /** True if this activity already has at least one realization row (hide “Submit data”). */
  activityHasRealization(activityId: string | null | undefined): boolean {
    if (!activityId) return false;
    const a = this.plan()?.activities?.find((x) => x.id === activityId);
    return a ? this.activityIsRealized(a) : false;
  }

  /** Show “Submit data” in the row menu for this activity. */
  canShowSubmitDataForActivity(activityId: string | null | undefined): boolean {
    return this.canCreateRealizationPermission() && this.canSubmitRealizationDataOnPlan() && !this.activityHasRealization(activityId);
  }

  // ── Menu 3 points (like document action) ─────────────────────────────────
  showActionMenu = signal(false);
  menuPosition = { top: 0, left: 0 };

  // ── Activity row 3-point menu ───────────────────────────────────────────
  activityMenuId = signal<string | null>(null);
  activityMenuPosition = { top: 0, left: 0 };

  /** Log realization (submit data) — plan year must match current calendar year. */
  showAddRealizationSidebar = signal(false);
  addRealizationActivityId = signal<string | null>(null);

  /** Edit existing realization (sidebar). */
  showEditRealizationSidebar = signal(false);
  realizedIdToEdit = signal<string | null>(null);

  // ── Add activity : année courante / future (formulaire simple) ──
  showAddActivitySidebar = signal(false);
  // ── Année passée : formulaire complet type hors plan → API plan-realized-draft (brouillon, pas hors plan) ──
  showPastYearRichCreate = signal(false);
  pastYearRichTitleKey = signal('PLANNED_ACTIVITY_CREATE.REALIZED_YEAR_DRAFT_TITLE');
  pastYearRichHintKey = signal<string | null>(null);
  // ── Edit planned activity sidebar ────────────────────────────────────────
  showEditActivitySidebar = signal(false);
  activityIdToEdit = signal<string | null>(null);

  // ── Approve confirmation (same pattern as change-request-detail) ────────
  showPlanApproveConfirm = signal(false);
  showOffPlanApproveConfirm = signal(false);
  offPlanApproveActivityId = signal<string | null>(null);

  // ── Reject modal ────────────────────────────────────────────────────────
  showRejectModal = signal(false);

  /** Off-plan activity reject (separate from plan reject). */
  showOffPlanRejectModal = signal(false);
  offPlanRejectActivityId = signal<string | null>(null);
  offPlanRejectComment = signal('');
  offPlanRejectError = signal('');

  // ── Confirmation modal (replace window.confirm) ──────────────────────────
  confirmOpen = signal(false);
  confirmTitle = signal<string>('');
  confirmMessage = signal<string>('');
  confirmButtonLabel = signal<string>('');
  private confirmAction: (() => void) | null = null;

  openConfirm(options: { title?: string; message: string; confirmLabel?: string; onConfirm: () => void }): void {
    this.confirmTitle.set(options.title ?? this.translate.instant('COMMON.CONFIRM'));
    this.confirmMessage.set(options.message);
    this.confirmButtonLabel.set(options.confirmLabel ?? this.translate.instant('COMMON.CONFIRM'));
    this.confirmAction = options.onConfirm;
    this.confirmOpen.set(true);
  }

  closeConfirm(): void {
    this.confirmOpen.set(false);
    this.confirmAction = null;
  }

  runConfirm(): void {
    const fn = this.confirmAction;
    this.closeConfirm();
    try { fn?.(); } catch {}
  }
  rejectComment = signal('');
  rejectActivityIds = signal<string[]>([]);
  rejectModalError = signal('');

  get canApprove(): boolean {
    return this.plan()?.can_approve ?? false;
  }

  get canReject(): boolean {
    return this.plan()?.can_reject ?? false;
  }

  canApproveOffPlan(activityId: string): boolean {
    const a = this.plan()?.activities?.find((x) => x.id === activityId);
    return a?.can_approve_off_plan ?? false;
  }

  canRejectOffPlan(activityId: string): boolean {
    const a = this.plan()?.activities?.find((x) => x.id === activityId);
    return a?.can_reject_off_plan ?? false;
  }

  canResubmitOffPlan(activityId: string): boolean {
    const a = this.plan()?.activities?.find((x) => x.id === activityId);
    return !!(a?.is_off_plan && a.status === 'REJECTED' && (a.activity_editable ?? false));
  }

  canSubmitModificationReview(activityId: string): boolean {
    const a = this.plan()?.activities?.find((x) => x.id === activityId);
    return !!(a?.can_submit_modification_review ?? false);
  }

  canResubmitModificationReview(activityId: string): boolean {
    const a = this.plan()?.activities?.find((x) => x.id === activityId);
    return !!(a?.can_resubmit_modification_review ?? false);
  }

  validationStepLabel(): string {
    const p = this.plan();
    if (!p || p.status !== 'SUBMITTED') return '';
    const step = p.validation_step;
    const mode = p.validation_mode || '101';
    const siteSteps = mode === '311' ? 3 : mode === '211' ? 2 : mode === '111' ? 1 : 0;
    if (typeof step === 'number' && step > 0 && step <= siteSteps) return `Pending level ${step}`;
    if (mode === '101') return this.translate.instant('PLAN_DETAIL.STEP_PENDING_CORPORATE_ONLY');
    if (typeof step === 'number' && step > siteSteps) return this.translate.instant('PLAN_DETAIL.STEP_PENDING_CORPORATE');
    return '';
  }

  /** Status label for display. */
  statusLabel(s: string): string {
    const m: Record<string, string> = {
      DRAFT: this.translate.instant('PLAN_DETAIL.STATUS_DRAFT'),
      SUBMITTED: this.translate.instant('PLAN_DETAIL.STATUS_SUBMITTED'),
      REJECTED: this.translate.instant('PLAN_DETAIL.STATUS_REJECTED'),
    };
    if (m[s]) return m[s];
    if (s === 'VALIDATED') {
      const p = this.plan();
      const u = p?.unlock_until;
      const open = u ? new Date(u) > new Date() : false;
      return open ? this.translate.instant('PLAN_DETAIL.STATUS_VALIDATED_UNLOCKED') : this.translate.instant('PLAN_DETAIL.STATUS_VALIDATED_LOCKED');
    }
    return s ?? '';
  }

  /** At least one realization row exists (API flag, or primary id for older payloads). */
  activityIsRealized(a: CsrPlanActivityDetail): boolean {
    if (a.has_realization === true) return true;
    if (a.has_realization === false) return false;
    return !!(a.primary_realization_id && String(a.primary_realization_id).trim());
  }

  /**
   * Badge in the realization column:
   * - Planned: future plan year, or plan draft/rejected, or submitted (not yet approved).
   * - In progress: plan approved (VALIDATED), plan year ≤ current year, no realization row yet.
   * - Completed: plan approved, realization on file, plan year ≤ current year (current or past).
   */
  activityRealizationUiStatus(a: CsrPlanActivityDetail): 'planned' | 'in_progress' | 'completed' {
    const p = this.plan();
    if (!p) return 'planned';
    const planYear = Number(p.year);
    if (!Number.isFinite(planYear)) return 'planned';
    const cy = this.currentYear;

    if (planYear > cy) {
      return 'planned';
    }
    const st = p.status;
    if (st === 'DRAFT' || st === 'REJECTED' || st === 'SUBMITTED') {
      return 'planned';
    }
    if (st !== 'VALIDATED') {
      return 'planned';
    }

    if (this.activityIsRealized(a)) {
      return 'completed';
    }
    return 'in_progress';
  }

  /** Activity submitted for validation (off-plan or in-plan modification on validated plan). */
  offPlanAwaitingValidation(a: CsrPlanActivityDetail): boolean {
    const p = this.plan();
    return !!(a.status === 'SUBMITTED' && p?.status === 'VALIDATED');
  }

  hasOffPlanPendingReview(): boolean {
    return (this.plan()?.activities ?? []).some((x) => this.offPlanAwaitingValidation(x));
  }

  /** Off-plan or in-plan modification rejected on a validated plan; row highlighted. */
  offPlanRejected(a: CsrPlanActivityDetail): boolean {
    const p = this.plan();
    return !!(a.status === 'REJECTED' && p?.status === 'VALIDATED');
  }

  hasOffPlanRejected(): boolean {
    return (this.plan()?.activities ?? []).some((x) => this.offPlanRejected(x));
  }

  activityRowTooltip(a: CsrPlanActivityDetail): string | null {
    if (this.offPlanAwaitingValidation(a)) {
      return this.translate.instant(
        a.is_off_plan ? 'PLAN_DETAIL.OFF_PLAN_ROW_TOOLTIP' : 'PLAN_DETAIL.ACTIVITY_MOD_PENDING_ROW_TOOLTIP',
      );
    }
    if (this.offPlanRejected(a)) {
      return this.translate.instant(
        a.is_off_plan ? 'PLAN_DETAIL.OFF_PLAN_REJECTED_TOOLTIP' : 'PLAN_DETAIL.ACTIVITY_MOD_REJECTED_TOOLTIP',
      );
    }
    return null;
  }

  /** True if plan has unlock_until in the future (open for edit period). */
  isUnlockUntilFuture(): boolean {
    const u = this.plan()?.unlock_until;
    if (!u) return false;
    return new Date(u) > new Date();
  }

  /** True if user can submit the plan for validation (DRAFT/REJECTED or VALIDATED with unlock period). */
  canSubmitForValidation(): boolean {
    const p = this.plan();
    if (!p) return false;
    if (!this.canSubmitPlan()) return false;
    if (p.status === 'DRAFT') return true;
    if (p.status === 'REJECTED') return true;
    if (p.status === 'VALIDATED' && this.isUnlockUntilFuture()) return true;
    return false;
  }

  /** Label for the submit button (differs when re-submitting modifications). */
  submitButtonLabel(): string {
    const p = this.plan();
    if (p?.status === 'VALIDATED' && this.isUnlockUntilFuture()) return this.translate.instant('PLAN_DETAIL.SUBMIT_MODIFICATIONS');
    return this.translate.instant('PLAN_DETAIL.SUBMIT_FOR_VALIDATION');
  }

  /** True if this specific activity can be edited (plan editable or activity individually unlocked). */
  canEditActivity(activityId: string): boolean {
    if (!this.canUpdateActivities()) return false;
    if (this.isCorporateUser()) return true;
    const p = this.plan();
    if (!p?.activities) return false;
    const a = p.activities.find((x) => x.id === activityId);
    return a?.activity_editable ?? false;
  }

  canDeleteActivity(activityId: string): boolean {
    return this.canDeleteActivities() && this.canEditActivity(activityId);
  }

  planKpiRate(value: number | null | undefined): string {
    if (value == null || Number.isNaN(Number(value))) return '–';
    return `${Number(value).toFixed(1)}%`;
  }

  planKpiMoney(value: number | null | undefined): string {
    if (value == null || Number.isNaN(Number(value))) return '–';
    return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })} €`;
  }

  /** True if plan can be edited: DRAFT/REJECTED always, or VALIDATED with unlock_until in the future. */
  canEditPlan(): boolean {
    if (!this.canUpdatePlanPermission()) return false;
    if (this.isCorporateUser()) return true;
    const p = this.plan();
    if (!p) return false;
    const u = p.unlock_until;
    const unlockFuture = u ? new Date(u) > new Date() : false;
    if (p.status === 'DRAFT' || p.status === 'REJECTED') return true;
    if (p.status === 'VALIDATED' && unlockFuture) return true;
    return false;
  }

  validationModeLabel(mode: string): string {
    if (mode === '311') return 'Validation level 3 (all levels)';
    if (mode === '211') return 'Validation level 2 (level1+level2+corporate)';
    if (mode === '111') return 'Validation level 1 (level1+corporate)';
    return this.translate.instant('PLAN_VALIDATION.MODE_CORPORATE_ONLY');
  }

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) {
      this.router.navigate(['/csr-plans']);
      return;
    }
    this.plansApi.get(id).subscribe({
      next: (p) => {
        this.plan.set(p);
        this.loading.set(false);
        const siteName = p.site_name ?? p.site_code ?? p.site_id ?? 'Plan';
        this.breadcrumb.setContext([siteName, String(p.year)]);
        const editFromTask = this.route.snapshot.queryParamMap.get('editActivity')?.trim();
        if (editFromTask && p.activities?.some((x) => x.id === editFromTask)) {
          this.goToEditActivity(editFromTask);
          this.router.navigate([], {
            relativeTo: this.route,
            queryParams: { editActivity: null },
            queryParamsHandling: 'merge',
            replaceUrl: true,
          });
        }
      },
      error: () => {
        this.loading.set(false);
        this.errorMsg.set('Plan introuvable');
      },
    });
  }

  ngOnDestroy(): void {
    this.breadcrumb.clearContext();
  }

  submitPlanForRealization(): void {
    const p = this.plan();
    if (!p || !this.canSubmitPlanForRealization()) return;
    this.openConfirm({
      title: this.translate.instant('COMMON.CONFIRM'),
      message: this.translate.instant('PLAN_DETAIL.SUBMIT_REALIZATION_REPORT_CONFIRM'),
      onConfirm: () => {
        this.actionLoading.set(true);
        this.plansApi.submitRealizationReport(p.id).subscribe({
          next: (updated) => {
            this.plansApi.get(p.id).subscribe({
              next: (detail) => {
                this.plan.set(detail);
                this.actionLoading.set(false);
              },
              error: () => {
                this.plan.set({ ...p, ...updated });
                this.actionLoading.set(false);
              },
            });
          },
          error: (err) => {
            this.actionLoading.set(false);
            this.errorMsg.set(err.error?.message || this.translate.instant('COMMON.ERROR'));
          },
        });
      },
    });
  }

  submitForValidation(): void {
    const p = this.plan();
    if (!p || !this.canSubmitForValidation()) return;
    const isResubmit = p.status === 'VALIDATED' && this.isUnlockUntilFuture();
    const msg = isResubmit
      ? 'Soumettre les modifications pour validation ?'
      : 'Soumettre ce plan pour validation ?';
    this.openConfirm({
      title: this.translate.instant('COMMON.CONFIRM'),
      message: msg,
      onConfirm: () => {
        this.actionLoading.set(true);
        this.plansApi.submitForValidation(p.id).subscribe({
          next: (updated) => {
            this.plan.set({ ...p, ...updated });
            this.actionLoading.set(false);
          },
          error: (err) => {
            this.actionLoading.set(false);
            this.errorMsg.set(err.error?.message || 'Erreur lors de la soumission');
          },
        });
      },
    });
  }

  openPlanApproveConfirm(): void {
    const p = this.plan();
    if (!p || p.status !== 'SUBMITTED' || !this.canApprove) return;
    this.showPlanApproveConfirm.set(true);
  }

  closePlanApproveConfirm(): void {
    this.showPlanApproveConfirm.set(false);
  }

  confirmPlanApprove(): void {
    const p = this.plan();
    if (!p || p.status !== 'SUBMITTED' || !this.canApprove) return;
    this.actionLoading.set(true);
    this.plansApi.approve(p.id).subscribe({
      next: (updated) => {
        this.plan.set({ ...p, ...updated });
        this.actionLoading.set(false);
        this.closePlanApproveConfirm();
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.errorMsg.set(err.error?.message || 'Erreur');
      },
    });
  }

  openRejectModal(): void {
    this.rejectComment.set('');
    this.rejectActivityIds.set([]);
    this.rejectModalError.set('');
    this.showRejectModal.set(true);
  }

  closeRejectModal(): void {
    this.showRejectModal.set(false);
    this.rejectComment.set('');
    this.rejectActivityIds.set([]);
    this.rejectModalError.set('');
  }

  toggleRejectActivity(activityId: string): void {
    const current = this.rejectActivityIds();
    const idx = current.indexOf(activityId);
    if (idx === -1) {
      this.rejectActivityIds.set([...current, activityId]);
    } else {
      this.rejectActivityIds.set(current.filter((id) => id !== activityId));
    }
  }

  isRejectActivitySelected(activityId: string): boolean {
    return this.rejectActivityIds().includes(activityId);
  }

  openOffPlanApproveConfirm(activityId: string): void {
    this.closeActivityMenu();
    this.offPlanApproveActivityId.set(activityId);
    this.showOffPlanApproveConfirm.set(true);
  }

  closeOffPlanApproveConfirm(): void {
    this.showOffPlanApproveConfirm.set(false);
    this.offPlanApproveActivityId.set(null);
  }

  confirmOffPlanApprove(): void {
    const activityId = this.offPlanApproveActivityId();
    const p = this.plan();
    if (!activityId || !p) return;
    this.actionLoading.set(true);
    this.activitiesApi.approveOffPlan(activityId).subscribe({
      next: () => {
        this.plansApi.get(p.id).subscribe({
          next: (updated) => {
            this.plan.set(updated);
            this.actionLoading.set(false);
            this.closeOffPlanApproveConfirm();
          },
          error: () => this.actionLoading.set(false),
        });
      },
      error: (err: { error?: { message?: string } }) => {
        this.actionLoading.set(false);
        this.errorMsg.set(err.error?.message ?? 'Erreur');
      },
    });
  }

  openOffPlanRejectModal(activityId: string): void {
    this.closeActivityMenu();
    this.offPlanRejectActivityId.set(activityId);
    this.offPlanRejectComment.set('');
    this.offPlanRejectError.set('');
    this.showOffPlanRejectModal.set(true);
  }

  closeOffPlanRejectModal(): void {
    this.showOffPlanRejectModal.set(false);
    this.offPlanRejectActivityId.set(null);
    this.offPlanRejectComment.set('');
    this.offPlanRejectError.set('');
  }

  submitOffPlanReject(): void {
    const comment = this.offPlanRejectComment().trim();
    if (!comment) {
      this.offPlanRejectError.set(this.translate.instant('PLAN_DETAIL.REJECT_REASON_REQUIRED'));
      return;
    }
    const id = this.offPlanRejectActivityId();
    const p = this.plan();
    if (!id || !p) return;
    this.offPlanRejectError.set('');
    this.actionLoading.set(true);
    this.activitiesApi.rejectOffPlan(id, { comment }).subscribe({
      next: () => {
        this.plansApi.get(p.id).subscribe({
          next: (updated) => {
            this.plan.set(updated);
            this.actionLoading.set(false);
            this.closeOffPlanRejectModal();
          },
          error: () => this.actionLoading.set(false),
        });
      },
      error: (err: { error?: { message?: string } }) => {
        this.actionLoading.set(false);
        this.offPlanRejectError.set(err.error?.message ?? 'Erreur');
      },
    });
  }

  submitActivityModificationReview(activityId: string): void {
    this.closeActivityMenu();
    const p = this.plan();
    if (!p) return;
    this.openConfirm({
      title: this.translate.instant('COMMON.CONFIRM'),
      message: this.translate.instant('PLAN_DETAIL.SUBMIT_ACTIVITY_FOR_REVIEW') + ' ?',
      onConfirm: () => {
        this.actionLoading.set(true);
        this.activitiesApi.submitModificationReview(activityId).subscribe({
          next: () => {
            this.plansApi.get(p.id).subscribe({
              next: (updated) => {
                this.plan.set(updated);
                this.actionLoading.set(false);
              },
              error: () => this.actionLoading.set(false),
            });
          },
          error: (err: { error?: { message?: string } }) => {
            this.actionLoading.set(false);
            this.errorMsg.set(err.error?.message ?? 'Erreur');
          },
        });
      },
    });
  }

  resubmitOffPlanActivity(activityId: string): void {
    this.closeActivityMenu();
    const p = this.plan();
    if (!p) return;
    if (!this.canResubmitOffPlan(activityId) && !this.canResubmitModificationReview(activityId)) {
      return;
    }
    this.openConfirm({
      title: this.translate.instant('COMMON.CONFIRM'),
      message: this.translate.instant('PLAN_DETAIL.OFF_PLAN_RESUBMIT') + ' ?',
      onConfirm: () => {
        this.actionLoading.set(true);
        this.activitiesApi.resubmitOffPlan(activityId).subscribe({
          next: () => {
            this.plansApi.get(p.id).subscribe({
              next: (updated) => {
                this.plan.set(updated);
                this.actionLoading.set(false);
              },
              error: () => this.actionLoading.set(false),
            });
          },
          error: (err: { error?: { message?: string } }) => {
            this.actionLoading.set(false);
            this.errorMsg.set(err.error?.message ?? 'Erreur');
          },
        });
      },
    });
  }

  submitReject(): void {
    const comment = this.rejectComment().trim();
    if (!comment) {
      this.rejectModalError.set(this.translate.instant('PLAN_DETAIL.REJECT_REASON_REQUIRED'));
      return;
    }
    const p = this.plan();
    if (!p || p.status !== 'SUBMITTED') return;
    this.rejectModalError.set('');
    this.actionLoading.set(true);
    const activityIds = this.rejectActivityIds();
    this.plansApi.reject(p.id, {
      comment,
      activity_ids: activityIds.length ? activityIds : undefined,
    }).subscribe({
      next: (updated) => {
        this.plan.set({ ...p, ...updated });
        this.actionLoading.set(false);
        this.closeRejectModal();
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.rejectModalError.set(err.error?.message || 'Erreur lors du rejet');
      },
    });
  }

  /** Rejected activities to display (id + label). */
  rejectedActivitiesList(): { id: string; label: string }[] {
    const p = this.plan();
    const ids = p?.rejected_activity_ids;
    if (!ids?.length || !p?.activities?.length) return [];
    return ids
      .map((id) => {
        const act = p.activities!.find((a) => a.id === id);
        return act ? { id, label: `${act.activity_number} – ${act.title}` } : null;
      })
      .filter((x): x is { id: string; label: string } => x != null);
  }

  addActivity(): void {
    const p = this.plan();
    if (!p || !this.canEditPlan()) return;
    const y = this.planYearValue();
    if (y != null && y < this.currentYear) {
      const unlock = p.status === 'VALIDATED' && this.isUnlockUntilFuture();
      this.pastYearRichTitleKey.set(
        unlock
          ? 'PLANNED_ACTIVITY_CREATE.REALIZED_YEAR_AMENDMENT_TITLE'
          : 'PLANNED_ACTIVITY_CREATE.REALIZED_YEAR_DRAFT_TITLE',
      );
      this.pastYearRichHintKey.set(
        unlock
          ? 'PLANNED_ACTIVITY_CREATE.REALIZED_YEAR_AMENDMENT_HINT'
          : 'PLANNED_ACTIVITY_CREATE.REALIZED_YEAR_RICH_HINT',
      );
      this.showPastYearRichCreate.set(true);
      return;
    }
    this.showAddActivitySidebar.set(true);
  }

  closeAddActivitySidebar(): void {
    this.showAddActivitySidebar.set(false);
  }

  closePastYearRichCreate(): void {
    this.showPastYearRichCreate.set(false);
  }

  onPastYearRichCreated(): void {
    this.closePastYearRichCreate();
    const p = this.plan();
    if (p) {
      this.plansApi.get(p.id).subscribe({
        next: (updated) => this.plan.set(updated),
      });
    }
  }

  onActivityAdded(): void {
    const p = this.plan();
    if (p) {
      this.plansApi.get(p.id).subscribe({
        next: (updated) => {
          this.plan.set(updated);
        },
      });
    }
  }

  toggleActionMenu(event: MouseEvent): void {
    event.stopPropagation();
    if (this.showActionMenu()) {
      this.showActionMenu.set(false);
      return;
    }
    const btn = event.currentTarget as HTMLElement;
    const rect = btn.getBoundingClientRect();
    this.menuPosition = { top: rect.bottom + 4, left: rect.right - 176 };
    this.showActionMenu.set(true);
  }

  closeActionMenu(): void {
    this.showActionMenu.set(false);
  }

  goToEdit(): void {
    const p = this.plan();
    if (p) this.router.navigate(['/csr-plans', p.id, 'edit']);
    this.closeActionMenu();
  }

  goToChangeRequest(planId: string): void {
    this.router.navigate(['/changes/create'], { queryParams: { planId } });
  }

  /** Navigate to change request create for a specific activity (plan must be VALIDATED and locked). */
  goToChangeRequestForActivity(planId: string, activityId: string): void {
    this.closeActivityMenu();
    this.router.navigate(['/changes/create'], { queryParams: { planId, activityId } });
  }

  /** True if user can request a change for the plan or an activity (plan validated and locked). */
  canRequestChange(): boolean {
    const p = this.plan();
    if (this.authStore.isValidatorLevel()) return false;
    if (this.isCorporateUser()) return false;
    return !!(p && p.status === 'VALIDATED' && !this.isUnlockUntilFuture());
  }

  @HostListener('document:click')
  onDocumentClick(): void {
    this.closeActionMenu();
    this.closeActivityMenu();
  }

  toggleActivityMenu(event: MouseEvent, activityId: string, openAbove: boolean): void {
    event.stopPropagation();
    if (this.activityMenuId() === activityId) {
      this.activityMenuId.set(null);
      return;
    }
    const btn = event.currentTarget as HTMLElement;
    const btnRect = btn.getBoundingClientRect();
    const menuWidth = 176;
    const left = initialFixedContextMenuLeft(btnRect, menuWidth);
    this.activityMenuPosition = { top: initialFixedContextMenuTopBelow(btnRect), left };
    this.activityMenuId.set(activityId);
    this.cdr.markForCheck();
    scheduleFixedContextMenuPosition({
      menuSelector: '[data-plan-detail-activity-menu]',
      btnRect,
      menuWidth,
      openAbove,
      initialLeft: left,
      isAlive: () => this.activityMenuId() === activityId,
      onApply: (top, l) => {
        this.activityMenuPosition = { top, left: l };
        this.cdr.detectChanges();
      },
    });
  }

  closeActivityMenu(): void {
    this.activityMenuId.set(null);
  }

  openAddRealizationFromMenu(activityId: string): void {
    this.closeActivityMenu();
    const p = this.plan();
    if (!p?.id || !this.canShowSubmitDataForActivity(activityId)) return;
    this.addRealizationActivityId.set(activityId);
    this.showAddRealizationSidebar.set(true);
  }

  closeAddRealizationSidebar(): void {
    this.showAddRealizationSidebar.set(false);
    this.addRealizationActivityId.set(null);
  }

  onRealizationCreatedFromMenu(): void {
    this.closeAddRealizationSidebar();
    const p = this.plan();
    if (p) {
      this.plansApi.get(p.id).subscribe({ next: (updated) => this.plan.set(updated) });
    }
  }

  deletePlan(): void {
    const p = this.plan();
    if (!p || (!this.isCorporateUser() && p.status !== 'DRAFT' && p.status !== 'REJECTED')) return;
    this.openConfirm({
      title: this.translate.instant('COMMON.CONFIRM'),
      message: 'Supprimer définitivement ce plan et toutes ses activités ?',
      confirmLabel: this.translate.instant('COMMON.DELETE'),
      onConfirm: () => {
        this.actionLoading.set(true);
        this.plansApi.delete(p.id).subscribe({
          next: () => {
            this.router.navigate(['/csr-plans']);
          },
          error: (err) => {
            this.actionLoading.set(false);
            this.errorMsg.set(err.error?.message || 'Erreur lors de la suppression');
          },
        });
      },
    });
  }

  back(): void {
    this.location.back();
  }

  goToActivityDetail(activityId: string): void {
    this.closeActivityMenu();
    const year = this.plan()?.year;
    const qp = year != null ? { year } : {};
    const act = this.plan()?.activities?.find((x) => x.id === activityId);
    const rid = act?.primary_realization_id?.trim();

    if (rid) {
      this.router.navigate(['/realized-csr', rid]);
      return;
    }

    if (this.activityHasRealization(activityId)) {
      this.realizedApi.list({ activity_id: activityId }).subscribe({
        next: (rows: RealizedCsr[]) => {
          const firstId = rows[0]?.id;
          if (firstId) {
            this.router.navigate(['/realized-csr', firstId]);
          } else {
            this.router.navigate(['/planned-activity', activityId], { queryParams: qp });
          }
        },
        error: () => {
          this.router.navigate(['/planned-activity', activityId], { queryParams: qp });
        },
      });
      return;
    }

    this.router.navigate(['/planned-activity', activityId], { queryParams: qp });
  }

  goToEditActivity(activityId: string): void {
    this.closeActivityMenu();
    if (!this.canEditActivity(activityId)) return;

    // Current/future plans: keep activity edit planned-only.
    // Realized data is handled through the dedicated realization sidebar flow.
    if (!this.isPastYearPlan()) {
      this.activityIdToEdit.set(activityId);
      this.showEditActivitySidebar.set(true);
      return;
    }

    // Past-year plans: use the combined planned+realized edit path when realization exists.
    if (this.activityHasRealization(activityId)) {
      const act = this.plan()?.activities?.find((x) => x.id === activityId);
      const rid = act?.primary_realization_id?.trim();
      if (rid) {
        this.realizedIdToEdit.set(rid);
        this.showEditRealizationSidebar.set(true);
        return;
      }
      this.realizedApi.list({ activity_id: activityId }).subscribe({
        next: (rows: RealizedCsr[]) => {
          const firstId = rows[0]?.id;
          if (firstId) {
            this.realizedIdToEdit.set(firstId);
            this.showEditRealizationSidebar.set(true);
          } else {
            this.activityIdToEdit.set(activityId);
            this.showEditActivitySidebar.set(true);
          }
        },
        error: () => {
          this.activityIdToEdit.set(activityId);
          this.showEditActivitySidebar.set(true);
        },
      });
      return;
    }

    this.activityIdToEdit.set(activityId);
    this.showEditActivitySidebar.set(true);
  }

  closeEditActivitySidebar(): void {
    this.showEditActivitySidebar.set(false);
    this.activityIdToEdit.set(null);
  }

  closeEditRealizationSidebar(): void {
    this.showEditRealizationSidebar.set(false);
    this.realizedIdToEdit.set(null);
  }

  onActivityUpdated(): void {
    this.closeEditActivitySidebar();
    const p = this.plan();
    if (p) {
      this.plansApi.get(p.id).subscribe({ next: (updated) => this.plan.set(updated) });
    }
  }

  onRealizationUpdatedFromPlan(): void {
    this.closeEditRealizationSidebar();
    const p = this.plan();
    if (p) {
      this.plansApi.get(p.id).subscribe({ next: (updated) => this.plan.set(updated) });
    }
  }

  deleteActivity(activityId: string): void {
    this.closeActivityMenu();
    // Align with per-activity `activity_editable` (e.g. rejected off-plan on a locked VALIDATED plan).
    if (!this.canDeleteActivities() || !this.canEditActivity(activityId)) return;
    const planId = this.plan()?.id;
    if (!planId) return;
    this.openConfirm({
      title: this.translate.instant('COMMON.CONFIRM'),
      message: 'Supprimer définitivement cette activité ?',
      confirmLabel: this.translate.instant('COMMON.DELETE'),
      onConfirm: () => {
        this.actionLoading.set(true);
        this.activitiesApi.delete(activityId).subscribe({
          next: () => {
            this.errorMsg.set('');
            this.plansApi.get(planId).subscribe({
              next: (p) => {
                this.plan.set(p);
                this.actionLoading.set(false);
              },
              error: () => this.actionLoading.set(false),
            });
          },
          error: (err: { error?: { message?: string } }) => {
            this.actionLoading.set(false);
            this.errorMsg.set(err.error?.message ?? 'Erreur lors de la suppression');
          },
        });
      },
    });
  }
}
