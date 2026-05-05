import { Component, inject, OnInit, OnDestroy, signal, computed } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { RouterLink } from '@angular/router';
import { TranslateModule } from '@ngx-translate/core';
import { CsrPlansApi } from '../api/csr-plans-api';
import type { CsrPlan, UpdateCsrPlanPayload } from '../models/csr-plan.model';
import { BreadcrumbService } from '@core/services/breadcrumb.service';

@Component({
  selector: 'app-plan-edit',
  standalone: true,
  imports: [ReactiveFormsModule, CommonModule, RouterLink, TranslateModule],
  templateUrl: './plan-edit.html',
})
export class PlanEditComponent implements OnInit, OnDestroy {
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private location = inject(Location);
  private csrPlansApi = inject(CsrPlansApi);
  private breadcrumb = inject(BreadcrumbService);

  planForm!: FormGroup;
  plan = signal<CsrPlan | null>(null);
  loading = true;
  saving = false;
  errorMsg = '';
  currentYear = new Date().getFullYear();

  planId = computed(() => this.route.snapshot.paramMap.get('id'));

  ngOnInit(): void {
    this.planForm = this.fb.group({
      year: [this.currentYear, [Validators.required, Validators.min(2000), Validators.max(2100)]],
      validation_mode: ['101'],
      allocated_budget: [null as number | null],
      total_hc: [null as number | null],
    });

    const id = this.planId();
    if (!id) {
      this.router.navigate(['/csr-plans']);
      return;
    }
    this.csrPlansApi.get(id).subscribe({
      next: (p) => {
        const plan = p as CsrPlan;
        const isUnlockedValidated = plan.status === 'VALIDATED' && !!plan.unlock_until && new Date(plan.unlock_until) > new Date();
        if (plan.status !== 'DRAFT' && plan.status !== 'REJECTED' && !isUnlockedValidated) {
          this.errorMsg = 'Ce plan est verrouillé et ne peut pas être modifié.';
          this.loading = false;
          return;
        }
        this.plan.set(plan);
        this.planForm.patchValue({
          year: plan.year,
          validation_mode: plan.validation_mode || '101',
          allocated_budget: plan.allocated_budget ?? null,
          total_hc: plan.total_hc ?? null,
        });
        this.loading = false;
        const siteName = plan.site_name ?? plan.site_code ?? plan.site_id ?? 'Plan';
        this.breadcrumb.setContext([siteName, String(plan.year)]);
      },
      error: () => {
        this.errorMsg = 'Plan introuvable.';
        this.loading = false;
      },
    });
  }

  ngOnDestroy(): void {
    this.breadcrumb.clearContext();
  }

  submit(): void {
    if (this.planForm.invalid || !this.plan()) {
      this.planForm.markAllAsTouched();
      return;
    }
    const p = this.plan()!;
    this.saving = true;
    this.errorMsg = '';
    const raw = this.planForm.getRawValue();
    const selectedMode = ['101', '111', '211', '311'].includes(String(raw.validation_mode))
      ? (raw.validation_mode as '101' | '111' | '211' | '311')
      : '101';
    const payload: UpdateCsrPlanPayload = {
      year: Number(raw.year),
      validation_mode: selectedMode,
      allocated_budget: raw.allocated_budget != null && raw.allocated_budget !== '' ? Number(raw.allocated_budget) : null,
      total_hc: raw.total_hc != null && raw.total_hc !== '' ? Number(raw.total_hc) : null,
    };
    this.csrPlansApi.update(p.id, payload).subscribe({
      next: () => {
        this.saving = false;
        this.router.navigate(['/csr-plans', p.id]);
      },
      error: (err) => {
        this.saving = false;
        this.errorMsg = err.error?.message || 'Erreur lors de la mise à jour du plan.';
      },
    });
  }

  cancel(): void {
    this.location.back();
  }
}
