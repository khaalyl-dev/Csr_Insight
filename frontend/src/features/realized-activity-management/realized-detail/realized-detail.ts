import { Component, inject, OnInit, OnDestroy, signal } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { RealizedCsrApi } from '../api/realized-csr-api';
import type { RealizedCsr } from '../models/realized-csr.model';
import { RealizedEditComponent } from '../realized-edit/realized-edit';
import { DocumentsApi } from '@features/file-management/api/documents-api';
import type { Document } from '@features/file-management/models/document.model';
import { AuthStore } from '@core/services/auth-store';

const MONTHS = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];

@Component({
  selector: 'app-realized-detail',
  standalone: true,
  imports: [CommonModule, RouterModule, TranslateModule, RealizedEditComponent],
  templateUrl: './realized-detail.html',
})
export class RealizedDetailComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private location = inject(Location);
  private api = inject(RealizedCsrApi);
  private documentsApi = inject(DocumentsApi);
  private http = inject(HttpClient);
  private translate = inject(TranslateService);
  private authStore = inject(AuthStore);

  realized = signal<RealizedCsr | null>(null);
  documents = signal<Document[]>([]);
  /** Blob URLs for image previews (auth). */
  docBlobUrls = signal<Record<string, string>>({});
  private blobUrlsToRevoke: string[] = [];
  loading = signal(true);
  errorMsg = signal('');

  monthLabel(m: number): string {
    return MONTHS[m] ?? String(m);
  }

  participationDisplay(participants?: number | null, totalHc?: number | null): string {
    if (participants == null) return '–';
    if (totalHc == null) return String(participants);
    if (!totalHc) return `${participants}/${totalHc}`;
    const pct = Math.round((participants / totalHc) * 100);
    return `${participants}/${totalHc} (${pct}%)`;
  }

  canManageRealized(): boolean {
    return !this.authStore.isValidatorLevel() && this.realized()?.plan_editable !== false;
  }

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) {
      this.router.navigate(['/realized-csr']);
      return;
    }
    this.api.get(id).subscribe({
      next: (data) => {
        this.realized.set(data);
        this.loading.set(false);
        if (data?.activity_id) {
          this.loadDocuments(data.activity_id);
        }
      },
      error: (err) => {
        this.loading.set(false);
        this.errorMsg.set(err.error?.message ?? 'Réalisation introuvable');
      },
    });
  }

  private loadDocuments(activityId: string): void {
    this.documentsApi.listByEntity('ACTIVITY', activityId).subscribe({
      next: (list) => {
        const docs = list ?? [];
        this.documents.set(docs);
        // Create blob URLs for images so <img> works with auth.
        docs.filter((d) => this.isImageType(d)).forEach((doc) => {
          const url = this.documentsApi.getServeUrl(doc.file_path);
          this.http.get(url, { responseType: 'blob' }).subscribe({
            next: (blob) => {
              const blobUrl = URL.createObjectURL(blob);
              this.blobUrlsToRevoke.push(blobUrl);
              this.docBlobUrls.update((m) => ({ ...m, [doc.id]: blobUrl }));
            },
          });
        });
      },
      error: () => {},
    });
  }

  isImageType(doc: Document): boolean {
    const t = (doc.file_type || '').toLowerCase();
    return ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(t);
  }

  getDocUrl(doc: Document): string {
    const urls = this.docBlobUrls();
    return urls[doc.id] ?? this.documentsApi.getServeUrl(doc.file_path);
  }

  getDownloadUrl(doc: Document): string {
    return this.documentsApi.getDownloadUrl(doc.file_path);
  }

  previewDoc(doc: Document, ev?: Event): void {
    ev?.preventDefault();
    ev?.stopPropagation();
    // Use /serve for in-browser preview (pdf/images), fetched with auth.
    const url = this.documentsApi.getServeUrl(doc.file_path);
    this.http.get(url, { responseType: 'blob' }).subscribe({
      next: (blob) => {
        const blobUrl = URL.createObjectURL(blob);
        this.blobUrlsToRevoke.push(blobUrl);
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

  onRealizedUpdated(): void {
    this.closeEditSidebar();
    const r = this.realized();
    if (r?.id) {
      this.api.get(r.id).subscribe({
        next: (data) => this.realized.set(data),
      });
    }
  }

  showDeleteModal = signal(false);

  openDeleteModal(): void {
    this.errorMsg.set('');
    this.showDeleteModal.set(true);
  }

  closeDeleteModal(): void {
    this.showDeleteModal.set(false);
  }

  confirmDeleteRealization(): void {
    this.closeDeleteModal();
    this.deleteRealization();
  }

  private deleteRealization(): void {
    const r = this.realized();
    if (!r?.id) return;
    this.api.delete(r.id).subscribe({
      next: () => {
        this.router.navigate(['/realized-csr']);
      },
      error: (err) => {
        this.errorMsg.set(
          err.error?.message ?? this.translate.instant('REALIZED_DETAIL.DELETE_ERROR'),
        );
      },
    });
  }

  ngOnDestroy(): void {
    this.blobUrlsToRevoke.forEach((u) => URL.revokeObjectURL(u));
  }
}
