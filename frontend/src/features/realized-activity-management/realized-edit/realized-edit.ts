import { Component, inject, OnInit, ChangeDetectorRef, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { TranslateModule } from '@ngx-translate/core';
import { RealizedCsrApi } from '../api/realized-csr-api';
import type { RealizedCsr } from '../models/realized-csr.model';
import { CsrActivitiesApi } from '../api/csr-activities-api';
import { switchMap } from 'rxjs/operators';

@Component({
  selector: 'app-realized-edit',
  standalone: true,
  imports: [ReactiveFormsModule, CommonModule, TranslateModule],
  templateUrl: './realized-edit.html',
})
export class RealizedEditComponent implements OnInit {
  @Input() realizedId: string | null = null;
  @Input() sidebarMode = false;
  @Output() closed = new EventEmitter<void>();
  @Output() updated = new EventEmitter<void>();

  private fb = inject(FormBuilder);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private cdr = inject(ChangeDetectorRef);
  private api = inject(RealizedCsrApi);
  private activitiesApi = inject(CsrActivitiesApi);
  private location = inject(Location);

  form!: FormGroup;
  realized: RealizedCsr | null = null;
  loading = false;
  loadingData = true;
  errorMsg = '';

  ngOnInit(): void {
    this.form = this.fb.group({
      // Planned activity (editable here too)
      activity_number: ['', Validators.required],
      title: ['', Validators.required],
      description: [''],
      planned_budget: [null as number | null],
      collaboration_nature: [''],
      periodicity: [''],
      start_year: [null as number | null],
      edition: [null as number | null],
      organizer: [''],
      external_partner: [''],
      action_impact_target: [null as number | null],
      action_impact_unit_target: [''],
      action_impact_duration: [''],

      // Realized (editable)
      realized_budget: [null as number | null],
      participants: [null as number | null],
      total_hc: [null as number | null],
      action_impact_actual: [null as number | null],
      action_impact_unit: [''],
      realization_date: [''],
      comment: [''],
      contact_name: [''],
      contact_email: [''],
    });

    const id = this.realizedId ?? this.route.snapshot.paramMap.get('id');
    if (!id) {
      if (!this.sidebarMode) this.router.navigate(['/realized-csr']);
      return;
    }

    this.api.get(id).subscribe({
      next: (r) => {
        this.realized = r;
        if (r.plan_editable === false) {
          this.errorMsg = 'Le plan est verrouillé. Soumettez une demande de modification pour modifier cette réalisation.';
          this.loadingData = false;
          this.cdr.markForCheck();
          return;
        }
        const rd = r.realization_date ? (r.realization_date as string).substring(0, 10) : '';
        this.form.patchValue({
          activity_number: r.activity_number ?? '',
          title: r.activity_title ?? '',
          description: r.activity_description ?? '',
          planned_budget: r.planned_budget ?? null,
          collaboration_nature: r.collaboration_nature ?? '',
          periodicity: r.periodicity ?? '',
          start_year: r.start_year ?? null,
          edition: r.edition ?? null,
          organizer: r.organizer ?? '',
          external_partner: r.external_partner_name ?? '',
          action_impact_target: r.action_impact_target ?? null,
          action_impact_unit_target: r.action_impact_unit_target ?? '',
          action_impact_duration: r.action_impact_duration ?? '',

          realized_budget: r.realized_budget ?? null,
          participants: r.participants ?? null,
          total_hc: r.total_hc ?? null,
          action_impact_actual: r.action_impact_actual ?? null,
          action_impact_unit: r.action_impact_unit ?? '',
          realization_date: rd,
          comment: r.comment ?? '',
          contact_name: r.contact_name ?? '',
          contact_email: r.contact_email ?? '',
        });
        this.loadingData = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.loadingData = false;
        this.errorMsg = err.error?.message ?? 'Réalisation introuvable.';
        this.cdr.markForCheck();
      },
    });
  }

  submit(): void {
    if (!this.realized || this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const raw = this.form.getRawValue();
    this.loading = true;
    this.errorMsg = '';

    const plannedPayload = {
      category_id: this.realized.category_id ?? '',
      activity_number: raw.activity_number?.trim() || '',
      title: raw.title?.trim() || '',
      description: raw.description?.trim() || null,
      collaboration_nature: raw.collaboration_nature?.trim() || null,
      periodicity: raw.periodicity?.trim() || null,
      planned_budget: raw.planned_budget != null && raw.planned_budget !== '' ? Number(raw.planned_budget) : null,
      action_impact_target: raw.action_impact_target != null && raw.action_impact_target !== '' ? Number(raw.action_impact_target) : null,
      action_impact_unit: raw.action_impact_unit_target?.trim() || null,
      action_impact_duration: raw.action_impact_duration?.trim() || null,
      organizer: raw.organizer?.trim() || null,
      edition: raw.edition != null && raw.edition !== '' ? Number(raw.edition) : null,
      start_year: raw.start_year != null && raw.start_year !== '' ? Number(raw.start_year) : null,
      external_partner: raw.external_partner?.trim() || null,
    };

    const realizedPayload = {
      realized_budget: raw.realized_budget != null && raw.realized_budget !== '' ? Number(raw.realized_budget) : null,
      participants: raw.participants != null && raw.participants !== '' ? Number(raw.participants) : null,
      action_impact_actual: raw.action_impact_actual != null && raw.action_impact_actual !== '' ? Number(raw.action_impact_actual) : null,
      action_impact_unit: raw.action_impact_unit?.trim() || null,
      realization_date: raw.realization_date?.trim() ? raw.realization_date.substring(0, 10) : null,
      comment: raw.comment?.trim() || null,
      contact_name: raw.contact_name?.trim() || null,
      contact_email: raw.contact_email?.trim() || null,
    };

    this.activitiesApi
      .update(this.realized.activity_id, plannedPayload)
      .pipe(switchMap(() => this.api.update(this.realized!.id, realizedPayload)))
      .subscribe({
      next: () => {
        this.loading = false;
        if (this.sidebarMode) {
          this.updated.emit();
          this.closed.emit();
        } else {
          this.router.navigate(['/realized-csr']);
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
}
