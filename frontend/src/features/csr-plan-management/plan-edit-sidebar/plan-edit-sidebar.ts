import { Component, EventEmitter, Input, Output, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { TranslateModule } from '@ngx-translate/core';
import { CsrPlansApi } from '../api/csr-plans-api';
import type { CsrPlan, UpdateCsrPlanPayload } from '../models/csr-plan.model';
import { I18nService } from '@core/services/i18n.service';

@Component({
  selector: 'app-plan-edit-sidebar',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, TranslateModule],
  templateUrl: './plan-edit-sidebar.html',
  host: { class: 'flex flex-col flex-1 min-h-0 overflow-hidden block w-full' },
})
export class PlanEditSidebarComponent implements OnInit {
  private fb = inject(FormBuilder);
  private csrPlansApi = inject(CsrPlansApi);
  private i18n = inject(I18nService);

  @Input({ required: true }) plan!: CsrPlan;
  @Output() closed = new EventEmitter<void>();
  @Output() updated = new EventEmitter<void>();

  form!: FormGroup;
  saving = signal(false);
  errorMsg = signal<string>('');

  siteLabel = computed(() => this.plan?.site_name ?? this.plan?.site_code ?? this.plan?.site_id ?? '');

  ngOnInit(): void {
    this.form = this.fb.group({
      year: [this.plan.year, [Validators.required, Validators.min(2000), Validators.max(2100)]],
      validation_mode: [this.plan.validation_mode || '101'],
      allocated_budget: [this.plan.allocated_budget ?? null],
      total_hc: [this.plan.total_hc ?? null],
    });
  }

  close(): void {
    if (this.saving()) return;
    this.closed.emit();
  }

  submit(): void {
    if (this.saving()) return;
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    this.errorMsg.set('');

    const raw = this.form.getRawValue();
    const selectedMode = ['101', '111', '211', '311'].includes(String(raw.validation_mode))
      ? (raw.validation_mode as '101' | '111' | '211' | '311')
      : '101';
    const payload: UpdateCsrPlanPayload = {
      year: Number(raw.year),
      validation_mode: selectedMode,
      allocated_budget: raw.allocated_budget != null && raw.allocated_budget !== '' ? Number(raw.allocated_budget) : null,
      total_hc: raw.total_hc != null && raw.total_hc !== '' ? Number(raw.total_hc) : null,
    };

    this.csrPlansApi.update(this.plan.id, payload).subscribe({
      next: () => {
        this.saving.set(false);
        this.updated.emit();
        this.closed.emit();
      },
      error: (err) => {
        this.saving.set(false);
        this.errorMsg.set(err?.error?.message || this.i18n.t('PLAN_EDIT.UPDATE_ERROR'));
      },
    });
  }
}

