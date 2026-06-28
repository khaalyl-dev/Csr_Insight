import { ChangeDetectorRef, Component, computed, signal, inject, OnInit, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { CsrActivitiesApi, type PlannedActivityListItem } from '../api/csr-activities-api';
import { PlannedActivityEditComponent } from '../planned-activity-edit/planned-activity-edit';
import { RealizedCreateSidebarComponent } from '@features/realized-activity-management/realized-create-sidebar/realized-create-sidebar';
import { AuthStore } from '@core/services/auth-store';
import {
  initialFixedContextMenuLeft,
  initialFixedContextMenuTopBelow,
  scheduleFixedContextMenuPosition,
} from '@core/utils/fixed-context-menu';

@Component({
  selector: 'app-planned-activities-list',
  standalone: true,
  imports: [CommonModule, RouterModule, TranslateModule, PlannedActivityEditComponent, RealizedCreateSidebarComponent],
  templateUrl: './planned-activities-list.html',
})
export class PlannedActivitiesListComponent implements OnInit {
  private api = inject(CsrActivitiesApi);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);
  private authStore = inject(AuthStore);
  private translate = inject(TranslateService);
  private readonly currentYear = new Date().getFullYear();
  private readonly exportColumns: Array<{ key: string; label: string }> = [
    { key: 'activity_number', label: 'Activity N' },
    { key: 'region', label: 'Region' },
    { key: 'country', label: 'Country' },
    { key: 'site_name', label: 'Plant' },
    { key: 'title', label: 'Title' },
    { key: 'description', label: 'Description' },
    { key: 'category_name', label: 'Category' },
    { key: 'lifecycle_status', label: 'Execution status' },
    { key: 'collaboration_nature', label: 'Nature of collaboration' },
    { key: 'year', label: 'Year' },
    { key: 'start_year', label: 'Start year' },
    { key: 'edition', label: 'Edition' },
    { key: 'external_partner', label: 'External Partner' },
    { key: 'total_hc', label: 'Total HC' },
    { key: 'percentage_employees', label: '% of all HC' },
    { key: 'planned_budget', label: 'Planned Budget (EUR)' },
    { key: 'realized_budget', label: 'Realized Budget (EUR)' },
    { key: 'impact_actual', label: 'Impact N' },
    { key: 'impact_unit', label: 'Impact Unit' },
    { key: 'organizer', label: 'Organizer' },
    { key: 'external_partner_count', label: '# of External Partners' },
    { key: 'is_off_plan', label: 'Is off plan' },
  ];

  activeMenuActivity: PlannedActivityListItem | null = null;
  menuPosition = { top: 0, left: 0 };

  @HostListener('document:click')
  onDocumentClick(): void {
    this.closeMenu();
  }

  toggleMenu(activity: PlannedActivityListItem, event: MouseEvent, openAbove: boolean): void {
    event.stopPropagation();
    if (this.activeMenuActivity?.id === activity.id) {
      this.closeMenu();
      return;
    }
    const btn = event.currentTarget as HTMLElement;
    const btnRect = btn.getBoundingClientRect();
    const menuWidth = 176;
    const left = initialFixedContextMenuLeft(btnRect, menuWidth);
    this.menuPosition = { top: initialFixedContextMenuTopBelow(btnRect), left };
    this.activeMenuActivity = activity;
    const activityId = activity.id;
    this.cdr.markForCheck();
    scheduleFixedContextMenuPosition({
      menuSelector: '[data-planned-activities-row-menu]',
      btnRect,
      menuWidth,
      openAbove,
      initialLeft: left,
      isAlive: () => this.activeMenuActivity?.id === activityId,
      onApply: (top, l) => {
        this.menuPosition = { top, left: l };
        this.cdr.detectChanges();
      },
    });
  }

  closeMenu(): void {
    this.activeMenuActivity = null;
  }

  goToDetail(activity: PlannedActivityListItem): void {
    this.closeMenu();
    this.router.navigate(['/planned-activity', activity.id]);
  }

  /** Uses API effective_status when present (validated plans), else stored status. */
  activityDisplayStatus(a: PlannedActivityListItem): string {
    const raw = ((a.effective_status ?? a.status) || '').toUpperCase();
    const keyMap: Record<string, string> = {
      COMPLETED: 'PLAN_DETAIL.REALIZATION_STATUS_COMPLETED',
      IN_PROGRESS: 'PLAN_DETAIL.REALIZATION_STATUS_IN_PROGRESS',
      PLANNED: 'PLAN_DETAIL.REALIZATION_STATUS_PLANNED',
      UNDER_REVIEW: 'PLAN_DETAIL.ACTIVITY_LIFECYCLE_UNDER_REVIEW',
      REJECTED: 'PLAN_DETAIL.STATUS_REJECTED',
      DRAFT: 'PLAN_DETAIL.STATUS_DRAFT',
      SUBMITTED: 'PLAN_DETAIL.STATUS_SUBMITTED',
      VALIDATED: 'PLAN_DETAIL.STATUS_VALIDATED',
      CANCELLED: 'PLAN_DETAIL.ACTIVITY_STATUS_CANCELLED',
      LOCKED: 'PLAN_DETAIL.STATUS_VALIDATED_LOCKED',
    };
    const k = keyMap[raw];
    return k ? this.translate.instant(k) : raw || '–';
  }

  /** KPI execution lifecycle (not validation workflow). */
  lifecycleDisplayStatus(a: PlannedActivityListItem): string {
    const raw = ((a.lifecycle_status ?? a.kpi?.lifecycle_status) || '').toUpperCase();
    const keyMap: Record<string, string> = {
      DRAFT: 'PLANNED_ACTIVITIES.EXEC_LIFECYCLE_DRAFT',
      PLANNED: 'PLANNED_ACTIVITIES.EXEC_LIFECYCLE_PLANNED',
      PENDING: 'PLANNED_ACTIVITIES.EXEC_LIFECYCLE_PENDING',
      COMPLETED: 'PLANNED_ACTIVITIES.EXEC_LIFECYCLE_COMPLETED',
    };
    const k = keyMap[raw];
    return k ? this.translate.instant(k) : raw || '–';
  }

  canRequestChange(activity: PlannedActivityListItem): boolean {
    if (this.authStore.isValidatorLevel()) return false;
    return !!(
      activity.plan_id &&
      activity.plan_status === 'VALIDATED' &&
      activity.plan_editable === false
    );
  }

  canManageActivity(activity: PlannedActivityListItem): boolean {
    return !this.authStore.isValidatorLevel() && activity.plan_editable !== false;
  }

  canAddRealization(activity: PlannedActivityListItem): boolean {
    return !this.authStore.isValidatorLevel() && !!activity.plan_id && !this.isPastPlanYear(activity);
  }

  goToChangeRequest(activity: PlannedActivityListItem): void {
    if (!activity.plan_id) return;
    this.closeMenu();
    this.router.navigate(['/changes/create'], {
      queryParams: { planId: activity.plan_id, activityId: activity.id },
    });
  }

  showEditSidebar = signal(false);
  activityIdToEdit = signal<string | null>(null);
  planIdToEdit = signal<string | null>(null);
  planYearToEdit = signal<number | null>(null);

  goToEdit(activity: PlannedActivityListItem): void {
    this.closeMenu();
    this.activityIdToEdit.set(activity.id);
    this.planIdToEdit.set(activity.plan_id ?? null);
    this.planYearToEdit.set(activity.year ?? null);
    this.showEditSidebar.set(true);
  }

  closeEditSidebar(): void {
    this.showEditSidebar.set(false);
    this.activityIdToEdit.set(null);
    this.planIdToEdit.set(null);
    this.planYearToEdit.set(null);
  }

  onActivityUpdated(): void {
    this.closeEditSidebar();
    this.refresh();
  }

  showAddRealizationSidebar = signal(false);
  addRealizationPlanId = signal<string | null>(null);
  addRealizationActivityId = signal<string | null>(null);

  openAddRealization(activity: PlannedActivityListItem): void {
    this.closeMenu();
    this.addRealizationPlanId.set(activity.plan_id ?? null);
    this.addRealizationActivityId.set(activity.id);
    this.showAddRealizationSidebar.set(true);
  }

  closeAddRealizationSidebar(): void {
    this.showAddRealizationSidebar.set(false);
    this.addRealizationPlanId.set(null);
    this.addRealizationActivityId.set(null);
  }

  onRealizationCreated(): void {
    this.closeAddRealizationSidebar();
    this.refresh();
  }

  /** Past-year plan: realized data is edited on the activity, not via “add realization”. */
  isPastPlanYear(activity: PlannedActivityListItem): boolean {
    const y = activity.year;
    return y != null && y < this.currentYear;
  }

  deleteFromMenu(activity: PlannedActivityListItem): void {
    if (!confirm('Supprimer définitivement cette activité planifiée ?')) return;
    this.api.delete(activity.id).subscribe({
      next: () => {
        this.list.update((list) => list.filter((a) => a.id !== activity.id));
        this.closeMenu();
      },
      error: () => {},
    });
  }

  list = signal<PlannedActivityListItem[]>([]);
  loading = signal(true);
  exporting = signal(false);
  selectedYear = signal<number | null>(null);
  selectedPlanId = signal<string | null>(null);
  search = signal<string>('');

  sortColumn = signal<string>('year');
  sortDirection = signal<'asc' | 'desc'>('desc');

  /** Unique plans from current list (for filter dropdown). */
  plans = computed(() => {
    const items = this.list();
    const seen = new Set<string>();
    const out: { plan_id: string; site_name: string; year: number }[] = [];
    for (const a of items) {
      if (a.plan_id && !seen.has(a.plan_id)) {
        seen.add(a.plan_id);
        out.push({
          plan_id: a.plan_id,
          site_name: (a.site_name ?? a.site_code ?? '–') as string,
          year: a.year ?? 0,
        });
      }
    }
    return out.sort((a, b) => b.year - a.year || a.site_name.localeCompare(b.site_name));
  });

  filteredList = computed(() => {
    const items = this.list();
    const year = this.selectedYear();
    const planId = this.selectedPlanId();
    const q = this.search().toLowerCase().trim();
    const filtered = items.filter(item =>
      (!year || item.year === year) &&
      (!planId || item.plan_id === planId) &&
      (!q ||
        (item.title ?? '').toLowerCase().includes(q) ||
        (item.activity_number ?? '').toLowerCase().includes(q) ||
        (item.site_name ?? '').toLowerCase().includes(q) ||
        (item.site_code ?? '').toLowerCase().includes(q) ||
        (item.category_name ?? '').toLowerCase().includes(q) ||
        String(item.year).includes(q))
    );
    const col = this.sortColumn();
    const dir = this.sortDirection();
    const lifecycleOf = (x: PlannedActivityListItem) =>
      ((x.lifecycle_status ?? x.kpi?.lifecycle_status) ?? '').toString().toLowerCase();
    return [...filtered].sort((a, b) => {
      const valA =
        col === 'status'
          ? ((a.effective_status ?? a.status) ?? '').toString().toLowerCase()
          : col === 'lifecycle_status'
            ? lifecycleOf(a)
            : ((a as any)[col]?.toString().toLowerCase() ?? '');
      const valB =
        col === 'status'
          ? ((b.effective_status ?? b.status) ?? '').toString().toLowerCase()
          : col === 'lifecycle_status'
            ? lifecycleOf(b)
            : ((b as any)[col]?.toString().toLowerCase() ?? '');
      const numA = typeof (a as any)[col] === 'number' ? (a as any)[col] : parseFloat(valA) || 0;
      const numB = typeof (b as any)[col] === 'number' ? (b as any)[col] : parseFloat(valB) || 0;
      if (col === 'year' || col === 'planned_budget' || col === 'start_year' || col === 'edition' || col === 'external_partner_count') {
        if (numA < numB) return dir === 'asc' ? -1 : 1;
        if (numA > numB) return dir === 'asc' ? 1 : -1;
      } else {
        if (valA < valB) return dir === 'asc' ? -1 : 1;
        if (valA > valB) return dir === 'asc' ? 1 : -1;
      }
      return 0;
    });
  });

  sortBy(column: string): void {
    if (this.sortColumn() === column) {
      this.sortDirection.update(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      this.sortColumn.set(column);
      this.sortDirection.set(column === 'year' ? 'desc' : 'asc');
    }
  }

  totalRecords = computed(() => this.filteredList().length);
  totalBudget = computed(() => this.filteredList().reduce((sum, a) => sum + (a.planned_budget ?? 0), 0));

  years = computed(() => {
    const set = new Set(this.list().map(a => a.year).filter(y => y != null));
    return Array.from(set).sort((a, b) => (b ?? 0) - (a ?? 0));
  });

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

  private buildExportRows(): Array<Record<string, unknown>> {
    return this.filteredList().map((a) => ({
      activity_number: a.activity_number ?? '',
      region: (a as any).region ?? (a as any).site_region ?? '',
      country: (a as any).country ?? (a as any).site_country ?? '',
      site_name: a.site_name ?? a.site_code ?? '',
      title: a.title ?? '',
      description: (a as any).description ?? '',
      category_name: a.category_name ?? '',
      lifecycle_status: this.lifecycleDisplayStatus(a),
      collaboration_nature: (a as any).collaboration_nature ?? '',
      year: a.year ?? '',
      start_year: a.start_year ?? '',
      edition: a.edition ?? '',
      external_partner: (a as any).external_partner ?? '',
      total_hc: (a as any).total_hc ?? '',
      percentage_employees: (a as any).percentage_employees ?? '',
      planned_budget: this.formatMoney(a.planned_budget),
      realized_budget: this.formatMoney((a as any).realized_budget),
      impact_actual: (a as any).impact_actual ?? (a as any).action_impact_target ?? '',
      impact_unit: (a as any).impact_unit ?? (a as any).action_impact_unit ?? '',
      organizer: a.organizer ?? '',
      external_partner_count: this.countExternalPartners((a as any).external_partner ?? a.external_partner_name ?? ''),
      is_off_plan: ((a as any).is_off_plan ?? false) ? 'Yes' : 'No',
    }));
  }

  private countExternalPartners(value: string): number {
    return value
      .split(',')
      .map((item) => item.trim())
      .filter((item) => item.length > 0).length;
  }

  private formatMoney(amount: number | null | undefined): string {
    if (amount == null || Number.isNaN(Number(amount))) return '';
    return Number(amount).toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  private exportAsCsv(rows: Array<Record<string, unknown>>): void {
    const headers = this.exportColumns.map((c) => c.label);
    const body = rows.map((row) =>
      this.exportColumns.map((c) => `"${String(row[c.key] ?? '').replace(/"/g, '""')}"`).join(',')
    );
    const csv = [headers.join(','), ...body].join('\n');
    this.downloadBlob(new Blob([csv], { type: 'text/csv;charset=utf-8;' }), this.exportFilename('csv'));
  }

  private exportAsXlsx(rows: Array<Record<string, unknown>>): void {
    import('xlsx').then((XLSX) => {
      const normalized = rows.map((row) => {
        const out: Record<string, string | number | boolean> = {};
        this.exportColumns.forEach((c) => (out[c.label] = (row[c.key] as string | number | boolean) ?? ''));
        return out;
      });
      const worksheet = XLSX.utils.json_to_sheet(normalized);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Activities');
      XLSX.writeFile(workbook, this.exportFilename('xlsx'));
    });
  }

  private exportAsDoc(rows: Array<Record<string, unknown>>): void {
    const headerHtml = this.exportColumns.map((c) => `<th>${this.escapeHtml(c.label)}</th>`).join('');
    const bodyHtml = rows.map((row) => `<tr>${this.exportColumns.map((c) => `<td>${this.escapeHtml(String(row[c.key] ?? ''))}</td>`).join('')}</tr>`).join('');
    const html = `<!doctype html><html><head><meta charset="utf-8"><title>Activities</title></head><body><h2>Activities export</h2><p><strong>Generated at:</strong> ${this.escapeHtml(this.exportTimestamp())}<br><strong>Generated by:</strong> ${this.escapeHtml(this.exportUserLabel())}</p><table border="1" cellspacing="0" cellpadding="6"><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></body></html>`;
    this.downloadBlob(new Blob([html], { type: 'application/msword' }), this.exportFilename('doc'));
  }

  private exportAsPdf(rows: Array<Record<string, unknown>>): void {
    const headerHtml = this.exportColumns.map((c) => `<th>${this.escapeHtml(c.label)}</th>`).join('');
    const bodyHtml = rows.map((row) => `<tr>${this.exportColumns.map((c) => `<td>${this.escapeHtml(String(row[c.key] ?? ''))}</td>`).join('')}</tr>`).join('');
    const title = this.exportFilename('pdf');
    const printWindow = window.open('', '_blank');
    if (!printWindow) return;
    printWindow.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${title}</title><style>body{font-family:Arial,sans-serif;padding:20px}h1{font-size:18px;margin:0 0 12px}.meta{font-size:12px;color:#374151;margin:0 0 12px}table{border-collapse:collapse;width:100%;font-size:11px}th,td{border:1px solid #d1d5db;padding:6px;text-align:left}th{background:#f3f4f6}</style></head><body><h1>Planned activities export</h1><p class="meta"><strong>Generated at:</strong> ${this.escapeHtml(this.exportTimestamp())}<br><strong>Generated by:</strong> ${this.escapeHtml(this.exportUserLabel())}</p><table><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></body></html>`);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  }

  private exportFilename(ext: 'csv' | 'xlsx' | 'doc' | 'pdf'): string {
    const stamp = new Date().toISOString().slice(0, 10);
    return `planned_activities_${stamp}.${ext}`;
  }

  private exportTimestamp(): string {
    return new Date().toLocaleString();
  }

  private exportUserLabel(): string {
    const u = this.authStore.user();
    if (!u) return 'Unknown user';
    const name = `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim();
    if (name && u.email) return `${name} (${u.email})`;
    if (name) return name;
    return u.email ?? 'Unknown user';
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

  ngOnInit(): void {
    this.refresh();
  }

  refresh(): void {
    this.loading.set(true);
    this.api.list({ exclude_realized: false }).subscribe({
      next: (data) => {
        this.list.set(data);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
