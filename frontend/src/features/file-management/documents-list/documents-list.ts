import { ChangeDetectorRef, Component, OnInit, signal, computed, HostListener, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { TranslateModule } from '@ngx-translate/core';
import { UserAvatarNameComponent } from '@shared/components/user-avatar-name/user-avatar-name';
import { DocumentsApi } from '../api/documents-api';
import { Document } from '../models/document.model';
import { I18nService } from '@core/services/i18n.service';
import { AuthStore } from '@core/services/auth-store';
import {
  FIXED_CONTEXT_MENU_GAP,
  FIXED_CONTEXT_MENU_PAD,
  initialFixedContextMenuLeft,
  initialFixedContextMenuTopBelow,
  scheduleFixedContextMenuPosition,
} from '@core/utils/fixed-context-menu';

@Component({
  selector: 'app-documents-list',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslateModule, UserAvatarNameComponent],
  templateUrl: './documents-list.html',
  styleUrl: './documents-list.css',
})
export class DocumentsListComponent implements OnInit {
  private static readonly DOCUMENT_ACTIONS_MENU_HEIGHT_ESTIMATE = 200;

  private cdr = inject(ChangeDetectorRef);
  private authStore = inject(AuthStore);

  documents = signal<Document[]>([]);
  loading = signal(true);
  error = signal('');
  success = signal('');

  // ── Menu 3 points (overlay fixe) ─────────────────────────────────────────
  activeMenuId: string | null = null;
  activeMenuDoc: Document | null = null;
  menuPosition = { top: 0, left: 0 };

  // ── Modal Modifier ────────────────────────────────────────────────────────
  showEditModal = false;
  editingDoc: Document | null = null;
  editFileName = '';
  editFileType = '';
  editSiteId = '';
  sites = signal<{id: string, name: string}[]>([]);

  // ── Modal Supprimer ───────────────────────────────────────────────────────
  showDeleteModal = false;
  deletingDoc: Document | null = null;

  // ── Search, filter, sort ───────────────────────────────────────────────────
  searchQuery = signal('');
  filterType = signal<string>('');
  filterSiteId = signal<string>('');
  sortColumn = signal<'file_name' | 'file_type' | 'site_name' | 'uploaded_at' | 'updated_at' | 'uploader_name'>('file_name');
  sortDirection = signal<'asc' | 'desc'>('asc');

  filteredAndSortedDocuments = computed(() => {
    let list = this.documents();
    const q = (this.searchQuery() ?? '').trim().toLowerCase();
    if (q) {
      list = list.filter(d =>
        (d.file_name ?? '').toLowerCase().includes(q) ||
        (d.file_type ?? '').toLowerCase().includes(q) ||
        (d.site_name ?? '').toLowerCase().includes(q) ||
        (d.uploader_name ?? '').toLowerCase().includes(q)
      );
    }
    const type = (this.filterType() ?? '').trim();
    if (type) {
      list = list.filter(d => (d.file_type ?? '').toUpperCase() === type.toUpperCase());
    }
    const siteId = (this.filterSiteId() ?? '').trim();
    if (siteId) {
      list = list.filter(d => d.site_id === siteId);
    }
    const col = this.sortColumn();
    const dir = this.sortDirection();
    return [...list].sort((a, b) => {
      let va: string | number = '';
      let vb: string | number = '';
      switch (col) {
        case 'file_name': va = (a.file_name ?? '').toLowerCase(); vb = (b.file_name ?? '').toLowerCase(); break;
        case 'file_type': va = (a.file_type ?? '').toLowerCase(); vb = (b.file_type ?? '').toLowerCase(); break;
        case 'site_name': va = (a.site_name ?? '').toLowerCase(); vb = (b.site_name ?? '').toLowerCase(); break;
        case 'uploader_name': va = (a.uploader_name ?? '').toLowerCase(); vb = (b.uploader_name ?? '').toLowerCase(); break;
        case 'uploaded_at': va = new Date(a.uploaded_at ?? 0).getTime(); vb = new Date(b.uploaded_at ?? 0).getTime(); break;
        case 'updated_at': va = new Date(a.updated_at ?? 0).getTime(); vb = new Date(b.updated_at ?? 0).getTime(); break;
        default: break;
      }
      if (typeof va === 'string' && typeof vb === 'string') {
        const c = va.localeCompare(vb);
        return dir === 'asc' ? c : -c;
      }
      const n = (va as number) - (vb as number);
      return dir === 'asc' ? n : -n;
    });
  });

  setSort(column: 'file_name' | 'file_type' | 'site_name' | 'uploaded_at' | 'updated_at' | 'uploader_name') {
    if (this.sortColumn() === column) {
      this.sortDirection.update(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      this.sortColumn.set(column);
      this.sortDirection.set('asc');
    }
  }

  constructor(
    private documentsApi: DocumentsApi,
    private http: HttpClient,
    private i18n: I18nService,
  ) {}

  ngOnInit() {
    this.loadDocuments();
    this.loadSites();
  }

  @HostListener('document:click')
  onDocumentClick() {
    this.closeMenu();
  }

  loadDocuments() {
    this.loading.set(true);
    this.documentsApi.list().subscribe({
      next: (data) => {
        this.documents.set(data);
        this.loading.set(false);
      },
      error: () => {
        this.error.set(this.i18n.t('DOCUMENTS.MESSAGES.LOAD_ERROR'));
        this.loading.set(false);
      }
    });
  }

  loadSites() {
    this.http.get<any[]>('/api/sites').subscribe({
      next: (data) => this.sites.set(data.map(s => ({ id: s.id, name: s.name }))),
      error: () => {}
    });
  }

  // ── Stats par type de fichier (PDF, PNG, etc.) ────────────────────────────
  fileTypeStats = computed(() => {
    const map = new Map<string, { name: string; count: number }>();
    for (const doc of this.documents()) {
      const type = (doc.file_type ?? 'Autre').toUpperCase();
      if (!map.has(type)) {
        map.set(type, { name: type, count: 0 });
      }
      map.get(type)!.count++;
    }
    const stats = Array.from(map.values()).sort((a, b) => b.count - a.count);
    const max = Math.max(...stats.map(s => s.count), 1);
    return stats.map(s => ({ ...s, percent: Math.round((s.count / max) * 100) }));
  });

  totalDocuments = computed(() => this.documents().length);
  pinnedDocuments = computed(() => this.documents().filter(d => d.is_pinned));
  recentDocuments = computed(() =>
    [...this.documents()]
      .sort((a, b) => new Date(b.uploaded_at ?? '').getTime() - new Date(a.uploaded_at ?? '').getTime())
      .slice(0, 5)
  );

  // ── Menu 3 points ─────────────────────────────────────────────────────────
  /** Prefer opening above the anchor for the last two rows (viewport clipping). */
  documentMenuOpenAbove(doc: Document, section: 'recent' | 'pinned' | 'table'): boolean {
    const list =
      section === 'recent'
        ? this.recentDocuments()
        : section === 'pinned'
          ? this.pinnedDocuments()
          : this.filteredAndSortedDocuments();
    const n = list.length;
    if (n === 0) return false;
    const idx = list.findIndex((d) => d.id === doc.id);
    return idx >= 0 && idx >= n - 2;
  }

  toggleMenu(doc: Document, event: MouseEvent, openAbove: boolean) {
    if (!this.canManageDocuments()) return;
    event.stopPropagation();
    if (this.activeMenuId === doc.id) {
      this.closeMenu();
      return;
    }
    const btn = event.currentTarget as HTMLElement;
    const btnRect = btn.getBoundingClientRect();
    const menuWidth = 176;
    const left = initialFixedContextMenuLeft(btnRect, menuWidth);
    const initialTop = openAbove
      ? Math.max(
          FIXED_CONTEXT_MENU_PAD,
          btnRect.top -
            DocumentsListComponent.DOCUMENT_ACTIONS_MENU_HEIGHT_ESTIMATE -
            FIXED_CONTEXT_MENU_GAP,
        )
      : initialFixedContextMenuTopBelow(btnRect);
    this.menuPosition = {
      top: initialTop,
      left,
    };
    this.activeMenuId = doc.id;
    this.activeMenuDoc = doc;
    const docId = doc.id;
    this.cdr.markForCheck();
    scheduleFixedContextMenuPosition({
      menuSelector: '[data-documents-actions-menu]',
      btnRect,
      menuWidth,
      openAbove,
      initialLeft: left,
      isAlive: () => this.activeMenuId === docId,
      onApply: (top: number, l: number) => {
        this.menuPosition = { top, left: l };
        this.cdr.detectChanges();
      },
    });
  }

  closeMenu() {
    this.activeMenuId = null;
    this.activeMenuDoc = null;
  }

  // ── Épingler ──────────────────────────────────────────────────────────────
  togglePin(doc: Document) {
    if (!this.canManageDocuments()) return;
    this.documentsApi.togglePin(doc.id).subscribe({
      next: (res: { is_pinned: boolean }) => {
        this.documents.update(docs =>
          docs.map(d => d.id === doc.id ? { ...d, is_pinned: res.is_pinned } : d)
        );
      },
      error: () => this.error.set(this.i18n.t('DOCUMENTS.MESSAGES.PIN_ERROR'))
    });
    this.closeMenu();
  }

  // ── Modifier ──────────────────────────────────────────────────────────────
  openEditModal(doc: Document) {
    if (!this.canManageDocuments()) return;
    this.editingDoc = doc;
    this.editFileName = doc.file_name;
    this.editFileType = doc.file_type;
    this.editSiteId = doc.site_id;
    this.showEditModal = true;
    this.closeMenu();
  }

  closeEditModal() {
    this.showEditModal = false;
    this.editingDoc = null;
  }

  submitEdit() {
    if (!this.canManageDocuments()) return;
    if (!this.editingDoc || !this.editFileName.trim()) return;
    this.documentsApi.updateDocument(this.editingDoc.id, {
      file_name: this.editFileName.trim(),
      file_type: this.editFileType,
      site_id: this.editSiteId,
    }).subscribe({
      next: (updated) => {
        this.documents.update(docs =>
          docs.map(d => d.id === updated.id ? updated : d)
        );
        this.success.set(this.i18n.t('DOCUMENTS.MESSAGES.UPDATE_SUCCESS'));
        setTimeout(() => this.success.set(''), 3000);
        this.closeEditModal();
      },
      error: () => this.error.set(this.i18n.t('DOCUMENTS.MESSAGES.UPDATE_ERROR'))
    });
  }

  // ── Supprimer ─────────────────────────────────────────────────────────────
  openDeleteModal(doc: Document) {
    if (!this.canManageDocuments()) return;
    this.deletingDoc = doc;
    this.showDeleteModal = true;
    this.closeMenu();
  }

  closeDeleteModal() {
    this.showDeleteModal = false;
    this.deletingDoc = null;
  }

  confirmDelete() {
    if (!this.canManageDocuments()) return;
    if (!this.deletingDoc) return;
    this.documentsApi.deleteDocument(this.deletingDoc.id).subscribe({
      next: () => {
        this.documents.update(docs => docs.filter(d => d.id !== this.deletingDoc!.id));
        this.success.set(this.i18n.t('DOCUMENTS.MESSAGES.DELETE_SUCCESS'));
        setTimeout(() => this.success.set(''), 3000);
        this.closeDeleteModal();
      },
      error: () => this.error.set(this.i18n.t('DOCUMENTS.MESSAGES.DELETE_ERROR'))
    });
  }

  downloadFile(filePath: string, fileName?: string) {
    this.http.get(`/api/documents/download/${filePath}`, {
      responseType: 'blob'
    }).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = (fileName ?? filePath.split('/').pop() ?? 'document').trim() || 'document';
        a.click();
        window.URL.revokeObjectURL(url);
      },
      error: () => this.error.set(this.i18n.t('DOCUMENTS.MESSAGES.DOWNLOAD_ERROR'))
    });
  }

  // ── Couleurs (bar / légende) ──────────────────────────────────────────────
  fileTypeColors = [
    { bar: 'bg-brand-700',  dot: 'bg-brand-700',  text: 'text-brand-800' },
    { bar: 'bg-orange-500', dot: 'bg-orange-500', text: 'text-orange-600' },
    { bar: 'bg-brand-800',  dot: 'bg-brand-800',  text: 'text-brand-900' },
    { bar: 'bg-purple-500', dot: 'bg-purple-500', text: 'text-purple-600' },
    { bar: 'bg-cyan-500',   dot: 'bg-cyan-500',   text: 'text-cyan-600' },
    { bar: 'bg-yellow-500', dot: 'bg-yellow-500', text: 'text-yellow-600' },
    { bar: 'bg-red-500',    dot: 'bg-red-500',    text: 'text-red-600' },
  ];

  canManageDocuments(): boolean {
    return !this.authStore.isValidatorLevel();
  }

  getColor(index: number) {
    return this.fileTypeColors[index % this.fileTypeColors.length];
  }

  getFileIcon(fileType: string): string {
    const icons: Record<string, string> = {
      'PDF':  'fas fa-file-pdf',
      'DOCX': 'fas fa-file-word',
      'DOC':  'fas fa-file-word',
      'XLSX': 'fas fa-file-excel',
      'XLS':  'fas fa-file-excel',
      'PNG':  'fas fa-file-image',
      'JPG':  'fas fa-file-image',
      'JPEG': 'fas fa-file-image',
      'ZIP':  'fas fa-file-zipper',
      'PPT':  'fas fa-file-powerpoint',
      'PPTX': 'fas fa-file-powerpoint',
    };
    return icons[fileType?.toUpperCase()] || 'fas fa-file';
  }

  getTypeBadgeClass(fileType: string): string {
    const classes: Record<string, string> = {
      'PDF':  'bg-red-100 text-red-700',
      'DOCX': 'bg-brand-100 text-brand-800',
      'DOC':  'bg-brand-100 text-brand-800',
      'XLSX': 'bg-green-100 text-green-700',
      'XLS':  'bg-green-100 text-green-700',
      'PNG':  'bg-purple-100 text-purple-700',
      'JPG':  'bg-purple-100 text-purple-700',
      'JPEG': 'bg-purple-100 text-purple-700',
      'ZIP':  'bg-yellow-100 text-yellow-700',
      'PPT':  'bg-orange-100 text-orange-700',
      'PPTX': 'bg-orange-100 text-orange-700',
    };
    return classes[fileType?.toUpperCase()] || 'bg-gray-100 text-gray-600';
  }

  getFileIconColor(fileType: string): string {
    const colors: Record<string, string> = {
      'PDF':  'text-red-500',
      'DOCX': 'text-brand-700',
      'DOC':  'text-brand-700',
      'XLSX': 'text-green-500',
      'XLS':  'text-green-500',
      'PNG':  'text-purple-500',
      'JPG':  'text-purple-500',
      'JPEG': 'text-purple-500',
      'ZIP':  'text-yellow-500',
      'PPT':  'text-orange-500',
      'PPTX': 'text-orange-500',
    };
    return colors[fileType?.toUpperCase()] || 'text-gray-500';
  }

  formatDate(dateStr: string | null): string {
    if (!dateStr) return '—';
    const lang = this.profileLang();
    return new Date(dateStr).toLocaleDateString(lang === 'fr' ? 'fr-FR' : 'en-US', {
      day: '2-digit', month: 'short', year: 'numeric'
    });
  }

  formatDateRelative(dateStr: string | null): string {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000);
    if (diff < 60) return this.i18n.t('DOCUMENTS.TIME.JUST_NOW');
    if (diff < 3600) return this.i18n.t('DOCUMENTS.TIME.MIN_AGO').replace('{n}', String(Math.floor(diff / 60)));
    if (diff < 86400) return this.i18n.t('DOCUMENTS.TIME.HOUR_AGO').replace('{n}', String(Math.floor(diff / 3600)));
    if (diff < 604800) return this.i18n.t('DOCUMENTS.TIME.DAY_AGO').replace('{n}', String(Math.floor(diff / 86400)));
    return this.formatDate(dateStr);
  }

  private profileLang(): 'fr' | 'en' {
    const lang = (document?.documentElement?.lang || '').toLowerCase();
    return lang.startsWith('fr') ? 'fr' : 'en';
  }

}