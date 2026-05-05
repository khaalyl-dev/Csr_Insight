import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { CsrPlansApi, CsrPlanDetail } from '../api/csr-plans-api';
import type { CsrPlan } from '../models/csr-plan.model';
import { UserAvatarNameComponent } from '@shared/components/user-avatar-name/user-avatar-name';

@Component({
  selector: 'app-plan-validation',
  standalone: true,
  imports: [CommonModule, RouterModule, TranslateModule, UserAvatarNameComponent],
  templateUrl: './plan-validation.html',
})
export class PlanValidationComponent implements OnInit {
  private plansApi = inject(CsrPlansApi);
  private translate = inject(TranslateService);
  private router = inject(Router);

  plans = signal<CsrPlan[]>([]);
  loading = signal(true);
  errorMsg = signal('');
  actionLoading = signal<string | null>(null);

  // Reject modal
  showRejectModal = signal(false);
  planToReject = signal<CsrPlan | null>(null);
  planDetailForReject = signal<CsrPlanDetail | null>(null);
  rejectComment = signal('');
  rejectActivityIds = signal<string[]>([]);
  rejectModalError = signal('');
  rejectModalLoading = signal(false);

  // Approve confirmation (same UX as change-request-detail)
  approveConfirmOpen = signal(false);
  planToApprove = signal<CsrPlan | null>(null);

  validationStepLabel(plan: CsrPlan): string {
    if (plan.status !== 'SUBMITTED') return '';
    const step = plan.validation_step;
    const mode = plan.validation_mode || '101';
    const siteSteps = mode === '311' ? 3 : mode === '211' ? 2 : mode === '111' ? 1 : 0;
    if (typeof step === 'number' && step > 0 && step <= siteSteps) return `Pending level ${step}`;
    if (mode === '101') return this.translate.instant('PLAN_VALIDATION.STEP_PENDING_CORPORATE_ONLY');
    if (typeof step === 'number' && step > siteSteps) return this.translate.instant('PLAN_VALIDATION.STEP_PENDING_CORPORATE');
    return '';
  }

  validationModeLabel(mode: string): string {
    if (mode === '311') return 'Level 3';
    if (mode === '211') return 'Level 2';
    if (mode === '111') return 'Level 1';
    return 'Corporate only';
  }

  ngOnInit(): void {
    this.loadPlans();
  }

  /** Navigate to plan detail; ignores clicks on action buttons. */
  onPlanRowNavigate(planId: string, event: MouseEvent): void {
    const t = event.target as HTMLElement | null;
    if (t?.closest('button')) return;
    void this.router.navigate(['/csr-plans', planId]);
  }

  loadPlans(): void {
    this.loading.set(true);
    this.errorMsg.set('');
    this.plansApi.list({ status: 'SUBMITTED' }).subscribe({
      next: (data) => {
        this.plans.set(data);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.errorMsg.set(this.translate.instant('PLAN_VALIDATION.LOAD_ERROR'));
      },
    });
  }

  openApproveConfirm(plan: CsrPlan): void {
    if (plan.status !== 'SUBMITTED' || !plan.can_approve) return;
    this.planToApprove.set(plan);
    this.approveConfirmOpen.set(true);
  }

  closeApproveConfirm(): void {
    this.approveConfirmOpen.set(false);
    this.planToApprove.set(null);
  }

  confirmApprove(): void {
    const plan = this.planToApprove();
    if (!plan || plan.status !== 'SUBMITTED' || !plan.can_approve) return;
    this.actionLoading.set(plan.id);
    this.plansApi.approve(plan.id).subscribe({
      next: () => {
        this.actionLoading.set(null);
        this.closeApproveConfirm();
        this.loadPlans();
      },
      error: () => {
        this.actionLoading.set(null);
      },
    });
  }

  openRejectModal(plan: CsrPlan): void {
    if (plan.status !== 'SUBMITTED' || !plan.can_reject) return;
    this.planToReject.set(plan);
    this.rejectComment.set('');
    this.rejectActivityIds.set([]);
    this.rejectModalError.set('');
    this.showRejectModal.set(true);
    this.rejectModalLoading.set(true);
    this.plansApi.get(plan.id).subscribe({
      next: (detail) => {
        this.planDetailForReject.set(detail);
        this.rejectModalLoading.set(false);
      },
      error: () => {
        this.rejectModalLoading.set(false);
        this.rejectModalError.set(this.translate.instant('PLAN_VALIDATION.DETAIL_LOAD_ERROR'));
      },
    });
  }

  closeRejectModal(): void {
    this.showRejectModal.set(false);
    this.planToReject.set(null);
    this.planDetailForReject.set(null);
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

  submitReject(): void {
    const comment = this.rejectComment().trim();
    if (!comment) {
      this.rejectModalError.set(this.translate.instant('PLAN_VALIDATION.REJECT_REASON_REQUIRED'));
      return;
    }
    const plan = this.planToReject();
    if (!plan) return;
    this.rejectModalError.set('');
    this.actionLoading.set(plan.id);
    const activityIds = this.rejectActivityIds();
    this.plansApi.reject(plan.id, {
      comment,
      activity_ids: activityIds.length ? activityIds : undefined,
    }).subscribe({
      next: () => {
        this.actionLoading.set(null);
        this.closeRejectModal();
        this.loadPlans();
      },
      error: (err) => {
        this.actionLoading.set(null);
        this.rejectModalError.set(err.error?.message || 'Erreur lors du rejet');
      },
    });
  }
}
