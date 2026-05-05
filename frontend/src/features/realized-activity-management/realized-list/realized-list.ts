import { ChangeDetectorRef, Component, computed, signal, inject, OnInit, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule, ActivatedRoute } from '@angular/router';
import { TranslateModule } from '@ngx-translate/core';
import { RealizedCsrApi } from '../api/realized-csr-api';
import type { RealizedCsr } from '../models/realized-csr.model';
import { RealizedCreateSidebarComponent } from '../realized-create-sidebar/realized-create-sidebar';
import { RealizedEditComponent } from '../realized-edit/realized-edit';
import { AuthStore } from '@core/services/auth-store';
import {
  initialFixedContextMenuLeft,
  initialFixedContextMenuTopBelow,
  scheduleFixedContextMenuPosition,
} from '@core/utils/fixed-context-menu';

@Component({
  selector: 'app-realized-list',
  standalone: true,
  imports: [CommonModule, RouterModule, TranslateModule, RealizedCreateSidebarComponent, RealizedEditComponent],
  templateUrl: './realized-list.html'
})
export class RealizedListComponent implements OnInit {
  private api = inject(RealizedCsrApi);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private authStore = inject(AuthStore);
  private cdr = inject(ChangeDetectorRef);
  private readonly exportColumns: Array<{ key: string; label: string }> = [
    { key: 'activity_number', label: 'Activity N' },
    { key: 'region', label: 'Region' },
    { key: 'country', label: 'Country' },
    { key: 'site_name', label: 'Plant' },
    { key: 'activity_title', label: 'Title' },
    { key: 'activity_description', label: 'Description' },
    { key: 'category_name', label: 'Category' },
    { key: 'collaboration_nature', label: 'Nature of collaboration' },
    { key: 'year', label: 'Year' },
    { key: 'start_year', label: 'Start year' },
    { key: 'edition', label: 'Edition' },
    { key: 'external_partner_name', label: 'External Partner' },
    { key: 'total_hc', label: 'Total HC' },
    { key: 'percentage_employees', label: '% of all HC' },
    { key: 'planned_budget', label: 'Planned Budget (EUR)' },
    { key: 'realized_budget', label: 'Realized Budget (EUR)' },
    { key: 'action_impact_actual', label: 'Impact N' },
    { key: 'action_impact_unit', label: 'Impact Unit' },
    { key: 'organizer', label: 'Organizer' },
    { key: 'number_external_partners', label: '# of External Partners' },
    { key: 'is_off_plan', label: 'Is off plan' },
  ];

  activeMenuRealized: RealizedCsr | null = null;
  activeRequestChangeRealized: RealizedCsr | null = null;
  menuPosition = { top: 0, left: 0 };

  /** True if user can request a change for this realization (plan validated and locked, has plan_id and activity_id). */
  canRequestChange(r: RealizedCsr): boolean {
    if (this.authStore.isValidatorLevel()) return false;
    if (this.isCorporateUser()) return false;
    return !!(
      !r.plan_editable &&
      r.plan_status === 'VALIDATED' &&
      r.plan_id &&
      r.activity_id
    );
  }

  private isCorporateUser(): boolean {
    return (this.authStore.user()?.role ?? '').toLowerCase() === 'corporate';
  }

  canManageRealized(r: RealizedCsr): boolean {
    return !this.authStore.isValidatorLevel() && !!r.plan_editable;
  }

  canCreateRealized(): boolean {
    return !this.authStore.isValidatorLevel();
  }

  @HostListener('document:click')
  onDocumentClick(): void {
    this.closeMenu();
    this.closeRequestChangeMenu();
  }

  toggleRequestChangeMenu(r: RealizedCsr, event: MouseEvent, openAbove: boolean): void {
    event.stopPropagation();
    if (this.activeRequestChangeRealized?.id === r.id) {
      this.closeRequestChangeMenu();
      return;
    }
    this.closeMenu();
    const btn = event.currentTarget as HTMLElement;
    const btnRect = btn.getBoundingClientRect();
    const menuWidth = 224; // w-56
    const left = initialFixedContextMenuLeft(btnRect, menuWidth);
    this.menuPosition = { top: initialFixedContextMenuTopBelow(btnRect), left };
    this.activeRequestChangeRealized = r;
    const rid = r.id;
    this.cdr.markForCheck();
    scheduleFixedContextMenuPosition({
      menuSelector: '[data-realized-request-change-menu]',
      btnRect,
      menuWidth,
      openAbove,
      initialLeft: left,
      isAlive: () => this.activeRequestChangeRealized?.id === rid,
      onApply: (top, l) => {
        this.menuPosition = { top, left: l };
        this.cdr.detectChanges();
      },
    });
  }

  closeRequestChangeMenu(): void {
    this.activeRequestChangeRealized = null;
  }

  goToChangeRequest(r: RealizedCsr): void {
    if (!r.plan_id || !r.activity_id) return;
    this.closeRequestChangeMenu();
    this.router.navigate(['/changes/create'], { queryParams: { planId: r.plan_id, activityId: r.activity_id } });
  }

  goToDetail(r: RealizedCsr): void {
    this.closeMenu();
    this.closeRequestChangeMenu();
    this.router.navigate(['/realized-csr', r.id]);
  }

  toggleMenu(r: RealizedCsr, event: MouseEvent, openAbove: boolean): void {
    event.stopPropagation();
    if (this.activeMenuRealized?.id === r.id) {
      this.closeMenu();
      return;
    }
    this.closeRequestChangeMenu();
    const btn = event.currentTarget as HTMLElement;
    const btnRect = btn.getBoundingClientRect();
    const menuWidth = 176;
    const left = initialFixedContextMenuLeft(btnRect, menuWidth);
    this.menuPosition = { top: initialFixedContextMenuTopBelow(btnRect), left };
    this.activeMenuRealized = r;
    const rid = r.id;
    this.cdr.markForCheck();
    scheduleFixedContextMenuPosition({
      menuSelector: '[data-realized-row-menu]',
      btnRect,
      menuWidth,
      openAbove,
      initialLeft: left,
      isAlive: () => this.activeMenuRealized?.id === rid,
      onApply: (top, l) => {
        this.menuPosition = { top, left: l };
        this.cdr.detectChanges();
      },
    });
  }

  closeMenu(): void {
    this.activeMenuRealized = null;
  }

  showEditSidebar = signal(false);
  realizedIdToEdit = signal<string | null>(null);

  goToEdit(r: RealizedCsr): void {
    this.closeMenu();
    this.realizedIdToEdit.set(r.id);
    this.showEditSidebar.set(true);
  }

  closeEditSidebar(): void {
    this.showEditSidebar.set(false);
    this.realizedIdToEdit.set(null);
  }

  onRealizedUpdated(): void {
    this.closeEditSidebar();
    this.refresh();
  }

  deleteFromMenu(r: RealizedCsr): void {
    if (!confirm('Supprimer définitivement cette réalisation ?')) return;
    this.api.delete(r.id).subscribe({
      next: () => {
        this.list.update((list) => list.filter((x) => x.id !== r.id));
        this.closeMenu();
      },
      error: () => {},
    });
  }

  list = signal<RealizedCsr[]>([]);
  loading = signal(true);
  exporting = signal(false);
  selectedPlanId = signal<string | null>(null);
  search = signal<string>('');

  sortColumn = signal<string>('realization_date');
  sortDirection = signal<'asc' | 'desc'>('desc');

  /** Unique plans from current list (for filter dropdown). */
  plans = computed(() => {
    const items = this.list();
    const seen = new Set<string>();
    const out: { plan_id: string; site_name: string; year: number }[] = [];
    for (const r of items) {
      if (r.plan_id && !seen.has(r.plan_id)) {
        seen.add(r.plan_id);
        out.push({
          plan_id: r.plan_id,
          site_name: (r.site_name ?? '–') as string,
          year: this._realizationYear(r) ?? 0,
        });
      }
    }
    return out.sort((a, b) => b.year - a.year || a.site_name.localeCompare(b.site_name));
  });

  private _realizationYear(r: RealizedCsr): number | null {
    const d = r.realization_date;
    if (!d) return null;
    const y = parseInt(String(d).slice(0, 4), 10);
    return Number.isFinite(y) ? y : null;
  }

  filteredList = computed(() => {
    const items = this.list();
    const planId = this.selectedPlanId();
    const q = this.search().toLowerCase().trim();
    const filtered = items.filter(item =>
      (!planId || item.plan_id === planId) &&
      (!q ||
        (item.activity_title ?? '').toLowerCase().includes(q) ||
        (item.activity_number ?? '').toLowerCase().includes(q) ||
        (item.site_name ?? '').toLowerCase().includes(q) ||
        (item.realization_date ?? '').toLowerCase().includes(q))
    );
    const col = this.sortColumn();
    const dir = this.sortDirection();
    return [...filtered].sort((a, b) => {
      const valA = (a as any)[col]?.toString().toLowerCase() ?? '';
      const valB = (b as any)[col]?.toString().toLowerCase() ?? '';
      let numA: number, numB: number;
      if (col === 'activity_number') {
        // Natural sort: extract numbers for comparison (CSR 1 < CSR 2 < CSR 10 < CSR 100)
        const matchA = valA.match(/\d+/g);
        const matchB = valB.match(/\d+/g);
        numA = matchA?.length ? parseInt(matchA[matchA.length - 1], 10) : 0;
        numB = matchB?.length ? parseInt(matchB[matchB.length - 1], 10) : 0;
        if (numA !== numB) {
          if (numA < numB) return dir === 'asc' ? -1 : 1;
          if (numA > numB) return dir === 'asc' ? 1 : -1;
        }
        return dir === 'asc' ? (valA < valB ? -1 : valA > valB ? 1 : 0) : (valA < valB ? 1 : valA > valB ? -1 : 0);
      }
      numA = typeof (a as any)[col] === 'number' ? (a as any)[col] : parseFloat(valA) || 0;
      numB = typeof (b as any)[col] === 'number' ? (b as any)[col] : parseFloat(valB) || 0;
      if (col === 'planned_budget' || col === 'realized_budget' || col === 'participants' || col === 'total_hc') {
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
  totalBudget = computed(() => this.filteredList().reduce((sum, r) => sum + (r.realized_budget ?? 0), 0));

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
    return this.filteredList().map((r) => ({
      activity_number: r.activity_number ?? '',
      region: (r as any).region ?? (r as any).site_region ?? '',
      country: (r as any).country ?? (r as any).site_country ?? '',
      site_name: r.site_name ?? '',
      activity_title: r.activity_title ?? '',
      activity_description: r.activity_description ?? '',
      category_name: r.category_name ?? '',
      collaboration_nature: r.collaboration_nature ?? '',
      year: this._realizationYear(r) ?? '',
      start_year: r.start_year ?? '',
      edition: r.edition ?? '',
      external_partner_name: r.external_partner_name ?? '',
      total_hc: r.total_hc ?? '',
      percentage_employees: (r as any).percentage_employees ?? '',
      planned_budget: this.formatMoney(r.planned_budget),
      realized_budget: this.formatMoney(r.realized_budget),
      action_impact_actual: r.action_impact_actual ?? '',
      action_impact_unit: r.action_impact_unit ?? '',
      organizer: r.organizer ?? '',
      number_external_partners: r.number_external_partners ?? '',
      is_off_plan: r.is_off_plan ? 'Yes' : 'No',
    }));
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
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Realized Activities');
      XLSX.writeFile(workbook, this.exportFilename('xlsx'));
    });
  }

  private exportAsDoc(rows: Array<Record<string, unknown>>): void {
    const headerHtml = this.exportColumns.map((c) => `<th>${this.escapeHtml(c.label)}</th>`).join('');
    const bodyHtml = rows.map((row) => `<tr>${this.exportColumns.map((c) => `<td>${this.escapeHtml(String(row[c.key] ?? ''))}</td>`).join('')}</tr>`).join('');
    const html = `<!doctype html><html><head><meta charset="utf-8"><title>Realized Activities</title></head><body><h2>Realized activities export</h2><p><strong>Generated at:</strong> ${this.escapeHtml(this.exportTimestamp())}<br><strong>Generated by:</strong> ${this.escapeHtml(this.exportUserLabel())}</p><table border="1" cellspacing="0" cellpadding="6"><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></body></html>`;
    this.downloadBlob(new Blob([html], { type: 'application/msword' }), this.exportFilename('doc'));
  }

  private exportAsPdf(rows: Array<Record<string, unknown>>): void {
    const headerHtml = this.exportColumns.map((c) => `<th>${this.escapeHtml(c.label)}</th>`).join('');
    const bodyHtml = rows.map((row) => `<tr>${this.exportColumns.map((c) => `<td>${this.escapeHtml(String(row[c.key] ?? ''))}</td>`).join('')}</tr>`).join('');
    const title = this.exportFilename('pdf');
    const printWindow = window.open('', '_blank');
    if (!printWindow) return;
    printWindow.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${title}</title><style>body{font-family:Arial,sans-serif;padding:20px}h1{font-size:18px;margin:0 0 12px}.meta{font-size:12px;color:#374151;margin:0 0 12px}table{border-collapse:collapse;width:100%;font-size:11px}th,td{border:1px solid #d1d5db;padding:6px;text-align:left}th{background:#f3f4f6}</style></head><body><h1>Realized activities export</h1><p class="meta"><strong>Generated at:</strong> ${this.escapeHtml(this.exportTimestamp())}<br><strong>Generated by:</strong> ${this.escapeHtml(this.exportUserLabel())}</p><table><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></body></html>`);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  }

  private exportFilename(ext: 'csv' | 'xlsx' | 'doc' | 'pdf'): string {
    const stamp = new Date().toISOString().slice(0, 10);
    return `realized_activities_${stamp}.${ext}`;
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

  refresh(): void {
    this.loading.set(true);
    this.api.list().subscribe({
      next: (data) => {
        this.list.set(data);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
