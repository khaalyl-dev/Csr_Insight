import { Component, computed, signal, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule, ActivatedRoute } from '@angular/router';
import { TranslateModule } from '@ngx-translate/core';
import { CsrPlansApi } from '@features/csr-plan-management/api/csr-plans-api';
import type { CsrPlan } from '@features/csr-plan-management/models/csr-plan.model';
import { RealizedCreateSidebarComponent } from '../realized-create-sidebar/realized-create-sidebar';
import { AuthStore } from '@core/services/auth-store';

@Component({
  selector: 'app-realized-list',
  standalone: true,
  imports: [CommonModule, RouterModule, TranslateModule, RealizedCreateSidebarComponent],
  templateUrl: './realized-list.html',
})
export class RealizedListComponent implements OnInit {
  private plansApi = inject(CsrPlansApi);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private authStore = inject(AuthStore);

  private readonly exportColumns: Array<{ key: string; label: string }> = [
    { key: 'site_name', label: 'Site' },
    { key: 'country', label: 'Country' },
    { key: 'year', label: 'Year' },
    { key: 'validation_mode', label: 'Mode' },
    { key: 'activities_count', label: 'Activities' },
    { key: 'activities_realized_count', label: 'Activities with report' },
    { key: 'allocated_budget', label: 'Allocated budget (EUR)' },
    { key: 'budget_consumed', label: 'Budget consumed (EUR)' },
    { key: 'incidents_sum', label: 'Safety – incidents' },
    { key: 'involvement_rate', label: 'People – involvement (%)' },
    { key: 'action_delivery_rate', label: 'Quality – delivery (%)' },
    { key: 'action_execution_rate', label: 'Volume – execution (%)' },
    { key: 'budget_control_rate', label: 'Cost – budget control (%)' },
    { key: 'external_partners_sum', label: 'External partners' },
    { key: 'participants_vs_total_hc_rate', label: '% of total HC' },
  ];

  plans = signal<CsrPlan[]>([]);
  loading = signal(true);
  exporting = signal(false);
  selectedYear = signal<number | null>(null);
  search = signal<string>('');
  expandedPlanIds = signal<Set<string>>(new Set());

  sortColumn = signal<string>('year');
  sortDirection = signal<'asc' | 'desc'>('desc');

  showCreateSidebar = signal(false);
  initialPlanIdForSidebar: string | null = null;

  ngOnInit(): void {
    this.refresh();
    this.route.queryParamMap.subscribe((params) => {
      const planId = params.get('plan_id');
      this.initialPlanIdForSidebar = planId || null;
      if (planId) {
        this.showCreateSidebar.set(true);
        this.router.navigate([], { queryParams: { plan_id: null }, queryParamsHandling: 'merge', replaceUrl: true });
      }
    });
  }

  refresh(): void {
    this.loading.set(true);
    this.plansApi.list({ plan_type: 'realized', include_plan_kpis: true }).subscribe({
      next: (data) => {
        this.plans.set(Array.isArray(data) ? data.filter((p) => this.isApprovedPlan(p)) : []);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  private isApprovedPlan(plan: CsrPlan): boolean {
    return plan.status === 'VALIDATED' || plan.status === 'LOCKED';
  }

  private readonly currentYear = new Date().getFullYear();

  filteredPlans = computed(() => {
    const list = this.plans();
    const year = this.selectedYear();
    const q = this.search().toLowerCase().trim();
    const filtered = list.filter((plan) => {
      if (!this.isApprovedPlan(plan)) return false;
      const planYear = plan.year != null ? Number(plan.year) : NaN;
      const isPastYear = Number.isFinite(planYear) && planYear < this.currentYear;
      const earlySubmitted = !!plan.realization_report_submitted_at;
      if (!isPastYear && !earlySubmitted) return false;
      const yearOk = !year || (Number.isFinite(planYear) && planYear === year) || plan.year === year;
      return (
        yearOk &&
        (!q ||
          (plan.site_name ?? '').toLowerCase().includes(q) ||
          (plan.site_code ?? '').toLowerCase().includes(q) ||
          (plan.site_country ?? '').toLowerCase().includes(q) ||
          String(plan.year).includes(q))
      );
    });
    const col = this.sortColumn();
    const dir = this.sortDirection();
    return [...filtered].sort((a, b) => {
      const kpiVal = (p: CsrPlan, field: string): number => {
        const v = (p.plan_kpis as Record<string, unknown> | null | undefined)?.[field];
        return typeof v === 'number' && Number.isFinite(v) ? v : -1;
      };
      if (col.startsWith('kpi_')) {
        const field = col.slice(4);
        const numA = kpiVal(a, field);
        const numB = kpiVal(b, field);
        if (numA < numB) return dir === 'asc' ? -1 : 1;
        if (numA > numB) return dir === 'asc' ? 1 : -1;
        return 0;
      }
      if (col === 'allocated_budget') {
        const numA = this.planPlannedBudget(a) ?? -1;
        const numB = this.planPlannedBudget(b) ?? -1;
        if (numA < numB) return dir === 'asc' ? -1 : 1;
        if (numA > numB) return dir === 'asc' ? 1 : -1;
        return 0;
      }
      if (col === 'realization_progress') {
        const score = (p: CsrPlan) => {
          const rate = p.plan_kpis?.action_execution_rate;
          if (rate != null && Number.isFinite(Number(rate))) return Number(rate);
          const total = Number(p.activities_count ?? 0);
          if (!Number.isFinite(total) || total <= 0) return -1;
          const r = Number(p.activities_realized_count ?? 0);
          return (Math.max(0, r) / total) * 100;
        };
        const numA = score(a);
        const numB = score(b);
        if (numA < numB) return dir === 'asc' ? -1 : 1;
        if (numA > numB) return dir === 'asc' ? 1 : -1;
        return 0;
      }
      const valA = (a as any)[col]?.toString().toLowerCase() ?? '';
      const valB = (b as any)[col]?.toString().toLowerCase() ?? '';
      const numA = typeof (a as any)[col] === 'number' ? (a as any)[col] : parseFloat(valA) || 0;
      const numB = typeof (b as any)[col] === 'number' ? (b as any)[col] : parseFloat(valB) || 0;
      if (col === 'year' || col === 'budget_consumed' || col === 'activities_count') {
        if (numA < numB) return dir === 'asc' ? -1 : 1;
        if (numA > numB) return dir === 'asc' ? 1 : -1;
      } else {
        if (valA < valB) return dir === 'asc' ? -1 : 1;
        if (valA > valB) return dir === 'asc' ? 1 : -1;
      }
      return 0;
    });
  });

  filterYears = computed(() => {
    const years = new Set(this.plans().map((p) => p.year).filter((y): y is number => y != null));
    return Array.from(years).sort((a, b) => b - a);
  });

  totalPlans = computed(() => this.filteredPlans().length);
  totalBudgetConsumed = computed(() =>
    this.filteredPlans().reduce((sum, p) => sum + (p.budget_consumed ?? p.plan_kpis?.actual_budget_sum ?? 0), 0)
  );
  avgExecutionRate = computed(() => {
    const rates = this.filteredPlans()
      .map((p) => p.plan_kpis?.action_execution_rate)
      .filter((v): v is number => v != null && Number.isFinite(Number(v)))
      .map(Number);
    if (!rates.length) return null;
    return rates.reduce((a, b) => a + b, 0) / rates.length;
  });

  sortBy(column: string): void {
    if (this.sortColumn() === column) {
      this.sortDirection.update((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      this.sortColumn.set(column);
      this.sortDirection.set(column === 'year' || column === 'realization_progress' ? 'desc' : 'asc');
    }
  }

  executionProgressInfo(plan: CsrPlan): { pct: number; barWidth: number } | null {
    const rate = plan.plan_kpis?.action_execution_rate;
    if (rate != null && Number.isFinite(Number(rate))) {
      const pct = Number(rate);
      return { pct, barWidth: Math.min(100, Math.max(0, pct)) };
    }
    const total = Number(plan.activities_count ?? 0);
    if (!Number.isFinite(total) || total <= 0) return null;
    const raw = Number(plan.activities_realized_count ?? 0);
    const realized = Number.isFinite(raw) ? Math.max(0, raw) : 0;
    const pct = (realized / total) * 100;
    return { pct, barWidth: Math.min(100, Math.max(0, pct)) };
  }

  /** Allocated budget in CSR reports = sum of each activity's planned budget. */
  planPlannedBudget(plan: CsrPlan): number | null {
    const fromPlan = plan.total_estimated_budget;
    if (fromPlan != null && Number.isFinite(Number(fromPlan))) return Number(fromPlan);
    const fromKpi = plan.plan_kpis?.estimated_budget_sum;
    if (fromKpi != null && Number.isFinite(Number(fromKpi))) return Number(fromKpi);
    return null;
  }

  validationModeLabel(mode: string): string {
    if (mode === '311') return 'Level 3';
    if (mode === '211') return 'Level 2';
    if (mode === '111') return 'Level 1';
    return 'Corporate only';
  }

  planKpiRate(value: number | null | undefined): string {
    if (value == null || Number.isNaN(Number(value))) return '–';
    return `${Number(value).toFixed(1)}%`;
  }

  planKpiMoney(value: number | null | undefined): string {
    if (value == null || Number.isNaN(Number(value))) return '–';
    return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })} €`;
  }

  goToDetail(plan: CsrPlan): void {
    this.router.navigate(['/csr-plans', plan.id]);
  }

  toggleExpanded(planId: string, event: MouseEvent): void {
    event.stopPropagation();
    this.expandedPlanIds.update((set) => {
      const next = new Set(set);
      if (next.has(planId)) next.delete(planId);
      else next.add(planId);
      return next;
    });
  }

  isExpanded(planId: string): boolean {
    return this.expandedPlanIds().has(planId);
  }

  canCreateRealized(): boolean {
    return !this.authStore.isValidatorLevel() && this.authStore.hasPermission('realized_activity.create');
  }

  openCreateSidebar(): void {
    if (!this.canCreateRealized()) return;
    this.showCreateSidebar.set(true);
  }

  closeCreateSidebar(): void {
    this.showCreateSidebar.set(false);
  }

  onRealizedCreated(): void {
    this.refresh();
  }

  exportRows(format: 'csv' | 'xlsx' | 'doc' | 'pdf'): void {
    const rows = this.buildExportRows();
    if (!rows.length || this.exporting()) return;
    this.exporting.set(true);
    try {
      if (format === 'csv') this.exportAsCsv(rows);
      else if (format === 'xlsx') this.exportAsXlsx(rows);
      else if (format === 'doc') this.exportAsDoc(rows);
      else this.exportAsPdf(rows);
    } finally {
      this.exporting.set(false);
    }
  }

  private buildExportRows(): Array<Record<string, string | number>> {
    return this.filteredPlans().map((plan) => {
      const kpis = plan.plan_kpis;
      return {
        site_name: plan.site_name ?? plan.site_code ?? plan.site_id,
        country: plan.site_country ?? '',
        year: plan.year ?? '',
        validation_mode: this.validationModeLabel(plan.validation_mode),
        activities_count: plan.activities_count ?? 0,
        activities_realized_count: plan.activities_realized_count ?? 0,
        allocated_budget: this.formatMoney(this.planPlannedBudget(plan)),
        budget_consumed: this.formatMoney(plan.budget_consumed ?? kpis?.actual_budget_sum),
        incidents_sum: kpis?.incidents_sum ?? 0,
        involvement_rate: kpis?.involvement_rate ?? '',
        action_delivery_rate: kpis?.action_delivery_rate ?? '',
        action_execution_rate: kpis?.action_execution_rate ?? '',
        budget_control_rate: kpis?.budget_control_rate ?? '',
        external_partners_sum: kpis?.external_partners_sum ?? 0,
        participants_vs_total_hc_rate: kpis?.participants_vs_total_hc_rate ?? '',
      };
    });
  }

  private formatMoney(amount: number | null | undefined): string {
    if (amount == null || Number.isNaN(Number(amount))) return '';
    return Number(amount).toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  private exportAsCsv(rows: Array<Record<string, string | number>>): void {
    const headers = this.exportColumns.map((c) => c.label);
    const body = rows.map((row) =>
      this.exportColumns.map((c) => `"${String(row[c.key] ?? '').replace(/"/g, '""')}"`).join(',')
    );
    const csv = [headers.join(','), ...body].join('\n');
    this.downloadBlob(new Blob([csv], { type: 'text/csv;charset=utf-8;' }), this.exportFilename('csv'));
  }

  private exportAsXlsx(rows: Array<Record<string, string | number>>): void {
    import('xlsx').then((XLSX) => {
      const normalized = rows.map((row) => {
        const out: Record<string, string | number> = {};
        this.exportColumns.forEach((c) => (out[c.label] = row[c.key] ?? ''));
        return out;
      });
      const worksheet = XLSX.utils.json_to_sheet(normalized);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'CSR Reports');
      XLSX.writeFile(workbook, this.exportFilename('xlsx'));
    });
  }

  private exportAsDoc(rows: Array<Record<string, string | number>>): void {
    const headerHtml = this.exportColumns.map((c) => `<th>${this.escapeHtml(c.label)}</th>`).join('');
    const bodyHtml = rows
      .map((row) => `<tr>${this.exportColumns.map((c) => `<td>${this.escapeHtml(String(row[c.key] ?? ''))}</td>`).join('')}</tr>`)
      .join('');
    const html = `<!doctype html><html><head><meta charset="utf-8"><title>CSR Reports</title></head><body><h2>CSR reports export</h2><p><strong>Generated at:</strong> ${this.escapeHtml(this.exportTimestamp())}</p><table border="1" cellspacing="0" cellpadding="6"><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></body></html>`;
    this.downloadBlob(new Blob([html], { type: 'application/msword' }), this.exportFilename('doc'));
  }

  private exportAsPdf(rows: Array<Record<string, string | number>>): void {
    const headerHtml = this.exportColumns.map((c) => `<th>${this.escapeHtml(c.label)}</th>`).join('');
    const bodyHtml = rows
      .map((row) => `<tr>${this.exportColumns.map((c) => `<td>${this.escapeHtml(String(row[c.key] ?? ''))}</td>`).join('')}</tr>`)
      .join('');
    const title = this.exportFilename('pdf');
    const printWindow = window.open('', '_blank');
    if (!printWindow) return;
    printWindow.document.write(
      `<!doctype html><html><head><meta charset="utf-8"><title>${title}</title><style>body{font-family:Arial,sans-serif;padding:20px}table{border-collapse:collapse;width:100%;font-size:10px}th,td{border:1px solid #d1d5db;padding:4px;text-align:left}th{background:#f3f4f6}</style></head><body><h1>CSR reports export</h1><p><strong>Generated at:</strong> ${this.escapeHtml(this.exportTimestamp())}</p><table><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></body></html>`
    );
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  }

  private exportFilename(ext: 'csv' | 'xlsx' | 'doc' | 'pdf'): string {
    return `csr_reports_${new Date().toISOString().slice(0, 10)}.${ext}`;
  }

  private exportTimestamp(): string {
    return new Date().toLocaleString();
  }

  private downloadBlob(blob: Blob, filename: string): void {
    const link = document.createElement('a');
    const href = URL.createObjectURL(blob);
    link.href = href;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(href);
  }

  private escapeHtml(value: string): string {
    return value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
}
