/**
 * UserDetailComponent - Page détail utilisateur (corporate only).
 * Route: /admin/users/:id
 * Features: view user, activate/deactivate, generate password, manage site access (SITE_USER).
 */
import { Component, inject, signal, OnInit, input, output } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { FontAwesomeModule } from '@fortawesome/angular-fontawesome';
import { faArrowLeft, faKey, faBan, faCheck, faBuilding, faUser } from '@fortawesome/free-solid-svg-icons';
import { UsersApi, type UserWithSites, type UserAccessMatrix } from '../api/users-api';
import { SitesApi, type Site } from '@features/site-management/api/sites-api';

@Component({
  selector: 'app-user-detail',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FontAwesomeModule, TranslateModule],
  templateUrl: './user-detail.html',
})
export class UserDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly usersApi = inject(UsersApi);
  private readonly location = inject(Location);
  private readonly sitesApi = inject(SitesApi);
  private readonly fb = inject(FormBuilder);
  private readonly http = inject(HttpClient);
  private readonly translate = inject(TranslateService);
  readonly userId = input<string | null>(null);
  readonly closed = output<void>();
  readonly toast = output<{ type: 'success' | 'error'; message: string }>();

  protected readonly faArrowLeft = faArrowLeft;
  protected readonly faKey = faKey;
  protected readonly faBan = faBan;
  protected readonly faCheck = faCheck;
  protected readonly faBuilding = faBuilding;
  protected readonly faUser = faUser;

  user = signal<UserWithSites | null>(null);
  sites = signal<Site[]>([]);
  loading = signal(false);
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);
  saving = signal(false);
  actionLoading = signal<string | null>(null);
  showPasswordModal = signal(false);
  showRevokeSiteModal = signal(false);
  showGlobalPermissionsModal = signal(false);
  generatedPassword = signal<string | null>(null);
  avatarDisplayUrl = signal<string | null>(null);
  revokingSite = signal<{ site_id: string; site_name: string | null } | null>(null);
  permissionSaving = signal(false);
  readonly permissionActions = ['create', 'read', 'update', 'delete', 'approve', 'reject'] as const;
  readonly permissionResources = ['plan', 'activity'] as const;
  permissions = signal<UserAccessMatrix>({
    plan: { create: true, read: true, update: true, delete: true, approve: true, reject: true },
    activity: { create: true, read: true, update: true, delete: true, approve: true, reject: true },
  });
  siteAccessRows = signal<Array<{ site_id: string; grade: 'level_0' | 'level_1' | 'level_2' | 'level_3' }>>([]);
  globalPermissionKeys = signal<string[]>([]);
  readonly sitePermissionOptions = [
    { key: 'dashboard.read', labelKey: 'USER_DETAIL.PERM.DASHBOARD_READ' },
    { key: 'plan.read', labelKey: 'USER_DETAIL.PERM.PLAN_READ' },
    { key: 'plan.create', labelKey: 'USER_DETAIL.PERM.PLAN_CREATE' },
    { key: 'plan.update', labelKey: 'USER_DETAIL.PERM.PLAN_UPDATE' },
    { key: 'plan.delete', labelKey: 'USER_DETAIL.PERM.PLAN_DELETE' },
    { key: 'plan.upload_excel', labelKey: 'USER_DETAIL.PERM.PLAN_UPLOAD_EXCEL' },
    { key: 'plan.submit', labelKey: 'USER_DETAIL.PERM.PLAN_SUBMIT' },
    { key: 'plan.bulk_delete', labelKey: 'USER_DETAIL.PERM.PLAN_BULK_DELETE' },
    { key: 'plan.validate', labelKey: 'USER_DETAIL.PERM.PLAN_VALIDATE' },
    { key: 'activity.read', labelKey: 'USER_DETAIL.PERM.ACTIVITY_READ' },
    { key: 'activity.create', labelKey: 'USER_DETAIL.PERM.ACTIVITY_CREATE' },
    { key: 'activity.update', labelKey: 'USER_DETAIL.PERM.ACTIVITY_UPDATE' },
    { key: 'activity.delete', labelKey: 'USER_DETAIL.PERM.ACTIVITY_DELETE' },
    { key: 'activity.validate', labelKey: 'USER_DETAIL.PERM.ACTIVITY_VALIDATE' },
    { key: 'activity.submit_modification_review', labelKey: 'USER_DETAIL.PERM.ACTIVITY_SUBMIT_REVIEW' },
    { key: 'activity.resubmit', labelKey: 'USER_DETAIL.PERM.ACTIVITY_RESUBMIT' },
    { key: 'realized_activity.read', labelKey: 'USER_DETAIL.PERM.REALIZED_READ' },
    { key: 'realized_activity.create', labelKey: 'USER_DETAIL.PERM.REALIZED_CREATE' },
    { key: 'realized_activity.update', labelKey: 'USER_DETAIL.PERM.REALIZED_UPDATE' },
    { key: 'realized_activity.delete', labelKey: 'USER_DETAIL.PERM.REALIZED_DELETE' },
    { key: 'document.read', labelKey: 'USER_DETAIL.PERM.DOCUMENT_READ' },
    { key: 'document.update', labelKey: 'USER_DETAIL.PERM.DOCUMENT_UPDATE' },
    { key: 'document.delete', labelKey: 'USER_DETAIL.PERM.DOCUMENT_DELETE' },
    { key: 'change_request.read', labelKey: 'USER_DETAIL.PERM.CR_READ' },
    { key: 'change_request.create', labelKey: 'USER_DETAIL.PERM.CR_CREATE' },
    { key: 'change_request.review', labelKey: 'USER_DETAIL.PERM.CR_REVIEW' },
    { key: 'change_request.history', labelKey: 'USER_DETAIL.PERM.CR_HISTORY' },
    { key: 'site.read', labelKey: 'USER_DETAIL.PERM.SITE_READ' },
    { key: 'site.create', labelKey: 'USER_DETAIL.PERM.SITE_CREATE' },
    { key: 'site.update', labelKey: 'USER_DETAIL.PERM.SITE_UPDATE' },
    { key: 'site.delete', labelKey: 'USER_DETAIL.PERM.SITE_DELETE' },
    { key: 'category.read', labelKey: 'USER_DETAIL.PERM.CATEGORY_READ' },
    { key: 'category.create', labelKey: 'USER_DETAIL.PERM.CATEGORY_CREATE' },
    { key: 'category.update', labelKey: 'USER_DETAIL.PERM.CATEGORY_UPDATE' },
    { key: 'category.delete', labelKey: 'USER_DETAIL.PERM.CATEGORY_DELETE' },
    { key: 'user.read', labelKey: 'USER_DETAIL.PERM.USER_READ' },
    { key: 'user.create', labelKey: 'USER_DETAIL.PERM.USER_CREATE' },
    { key: 'user.update', labelKey: 'USER_DETAIL.PERM.USER_UPDATE' },
    { key: 'audit_log.read', labelKey: 'USER_DETAIL.PERM.AUDIT_READ' },
    { key: 'audit_log.export', labelKey: 'USER_DETAIL.PERM.AUDIT_EXPORT' },
    { key: 'notification.read', labelKey: 'USER_DETAIL.PERM.NOTIF_READ' },
    { key: 'notification.manage', labelKey: 'USER_DETAIL.PERM.NOTIF_MANAGE' },
    { key: 'task.read', labelKey: 'USER_DETAIL.PERM.TASK_READ' },
  ] as const;
  readonly sitePermissionCategories = [
    {
      key: 'dashboard',
      labelKey: 'USER_DETAIL.CAT.DASHBOARD',
      items: [
        { key: 'dashboard.read', labelKey: 'USER_DETAIL.PERM.DASHBOARD_READ_DETAIL' },
      ],
    },
    {
      key: 'plan',
      labelKey: 'USER_DETAIL.CAT.PLAN',
      items: [
        { key: 'plan.read', labelKey: 'USER_DETAIL.PERM.PLAN_READ' },
        { key: 'plan.create', labelKey: 'USER_DETAIL.PERM.PLAN_CREATE' },
        { key: 'plan.update', labelKey: 'USER_DETAIL.PERM.PLAN_UPDATE' },
        { key: 'plan.delete', labelKey: 'USER_DETAIL.PERM.PLAN_DELETE' },
        { key: 'plan.upload_excel', labelKey: 'USER_DETAIL.PERM.PLAN_UPLOAD_EXCEL' },
        { key: 'plan.submit', labelKey: 'USER_DETAIL.PERM.PLAN_SUBMIT' },
        { key: 'plan.bulk_delete', labelKey: 'USER_DETAIL.PERM.PLAN_BULK_DELETE' },
        { key: 'plan.validate', labelKey: 'USER_DETAIL.PERM.PLAN_VALIDATE' },
      ],
    },
    {
      key: 'activity',
      labelKey: 'USER_DETAIL.CAT.ACTIVITY',
      items: [
        { key: 'activity.read', labelKey: 'USER_DETAIL.PERM.ACTIVITY_READ' },
        { key: 'activity.create', labelKey: 'USER_DETAIL.PERM.ACTIVITY_CREATE' },
        { key: 'activity.update', labelKey: 'USER_DETAIL.PERM.ACTIVITY_UPDATE' },
        { key: 'activity.delete', labelKey: 'USER_DETAIL.PERM.ACTIVITY_DELETE' },
        { key: 'activity.validate', labelKey: 'USER_DETAIL.PERM.ACTIVITY_VALIDATE' },
        { key: 'activity.submit_modification_review', labelKey: 'USER_DETAIL.PERM.ACTIVITY_SUBMIT_REVIEW' },
        { key: 'activity.resubmit', labelKey: 'USER_DETAIL.PERM.ACTIVITY_RESUBMIT' },
      ],
    },
    {
      key: 'realized_activity',
      labelKey: 'USER_DETAIL.CAT.REALIZED_ACTIVITY',
      items: [
        { key: 'realized_activity.read', labelKey: 'USER_DETAIL.PERM.REALIZED_READ' },
        { key: 'realized_activity.create', labelKey: 'USER_DETAIL.PERM.REALIZED_CREATE' },
        { key: 'realized_activity.update', labelKey: 'USER_DETAIL.PERM.REALIZED_UPDATE' },
        { key: 'realized_activity.delete', labelKey: 'USER_DETAIL.PERM.REALIZED_DELETE' },
      ],
    },
    {
      key: 'document',
      labelKey: 'USER_DETAIL.CAT.DOCUMENT',
      items: [
        { key: 'document.read', labelKey: 'USER_DETAIL.PERM.DOCUMENT_READ' },
        { key: 'document.update', labelKey: 'USER_DETAIL.PERM.DOCUMENT_UPDATE' },
        { key: 'document.delete', labelKey: 'USER_DETAIL.PERM.DOCUMENT_DELETE' },
      ],
    },
    {
      key: 'change_request',
      labelKey: 'USER_DETAIL.CAT.CHANGE_REQUEST',
      items: [
        { key: 'change_request.read', labelKey: 'USER_DETAIL.PERM.CR_READ' },
        { key: 'change_request.create', labelKey: 'USER_DETAIL.PERM.CR_CREATE' },
        { key: 'change_request.review', labelKey: 'USER_DETAIL.PERM.CR_REVIEW' },
        { key: 'change_request.history', labelKey: 'USER_DETAIL.PERM.CR_HISTORY' },
      ],
    },
    {
      key: 'site',
      labelKey: 'USER_DETAIL.CAT.SITE',
      items: [
        { key: 'site.read', labelKey: 'USER_DETAIL.PERM.SITE_READ' },
        { key: 'site.create', labelKey: 'USER_DETAIL.PERM.SITE_CREATE' },
        { key: 'site.update', labelKey: 'USER_DETAIL.PERM.SITE_UPDATE' },
        { key: 'site.delete', labelKey: 'USER_DETAIL.PERM.SITE_DELETE' },
      ],
    },
    {
      key: 'category',
      labelKey: 'USER_DETAIL.CAT.CATEGORY',
      items: [
        { key: 'category.read', labelKey: 'USER_DETAIL.PERM.CATEGORY_READ' },
        { key: 'category.create', labelKey: 'USER_DETAIL.PERM.CATEGORY_CREATE' },
        { key: 'category.update', labelKey: 'USER_DETAIL.PERM.CATEGORY_UPDATE' },
        { key: 'category.delete', labelKey: 'USER_DETAIL.PERM.CATEGORY_DELETE' },
      ],
    },
    {
      key: 'user',
      labelKey: 'USER_DETAIL.CAT.USER_ADMIN',
      items: [
        { key: 'user.read', labelKey: 'USER_DETAIL.PERM.USER_READ' },
        { key: 'user.create', labelKey: 'USER_DETAIL.PERM.USER_CREATE' },
        { key: 'user.update', labelKey: 'USER_DETAIL.PERM.USER_UPDATE' },
      ],
    },
    {
      key: 'audit_log',
      labelKey: 'USER_DETAIL.CAT.AUDIT_LOG',
      items: [
        { key: 'audit_log.read', labelKey: 'USER_DETAIL.PERM.AUDIT_READ' },
        { key: 'audit_log.export', labelKey: 'USER_DETAIL.PERM.AUDIT_EXPORT' },
      ],
    },
    {
      key: 'notification',
      labelKey: 'USER_DETAIL.CAT.NOTIFICATION',
      items: [
        { key: 'notification.read', labelKey: 'USER_DETAIL.PERM.NOTIF_READ' },
        { key: 'notification.manage', labelKey: 'USER_DETAIL.PERM.NOTIF_MANAGE' },
      ],
    },
    {
      key: 'task',
      labelKey: 'USER_DETAIL.CAT.TASK',
      items: [
        { key: 'task.read', labelKey: 'USER_DETAIL.PERM.TASK_READ' },
      ],
    },
  ] as const;
  readonly rolePermissionCategoryKeys: Record<'SITE_USER' | 'CORPORATE_USER', string[]> = {
    // Based on sidebar modules available to site users.
    SITE_USER: [
      'dashboard',
      'plan',
      'activity',
      'realized_activity',
      'document',
      'change_request',
      'task',
    ],
    // Corporate users can access all permission categories.
    CORPORATE_USER: [
      'dashboard',
      'plan',
      'activity',
      'realized_activity',
      'document',
      'change_request',
      'site',
      'category',
      'user',
      'audit_log',
      'notification',
      'task',
    ],
  };
  readonly siteUserCreatorKeys = [
    'dashboard.read', 'task.read',
    'plan.read', 'plan.create', 'plan.update', 'plan.delete', 'plan.submit', 'plan.upload_excel', 'plan.bulk_delete',
    'activity.read', 'activity.create', 'activity.update', 'activity.delete', 'activity.submit_modification_review', 'activity.resubmit',
    'realized_activity.read', 'realized_activity.create', 'realized_activity.update', 'realized_activity.delete',
    'document.read', 'document.update', 'document.delete',
    'change_request.read', 'change_request.create', 'change_request.history',
  ] as const;
  readonly siteUserValidatorKeys = [
    'dashboard.read', 'task.read',
    'plan.read', 'plan.validate',
    'activity.read', 'activity.validate',
    'document.read',
    'change_request.read', 'change_request.review', 'change_request.history',
  ] as const;

  form = this.fb.group({
    site_ids: [[] as string[]],
    default_grade: ['level_0' as 'level_0' | 'level_1' | 'level_2' | 'level_3'],
  });
  profileForm = this.fb.group({
    first_name: [''],
    last_name: [''],
    email: [''],
    role: ['SITE_USER' as 'SITE_USER' | 'CORPORATE_USER'],
    password: [''],
  });

  ngOnInit(): void {
    const id = this.userId() ?? this.route.snapshot.paramMap.get('id');
    if (id) {
      this.loadUser(id);
    }
    this.loadSites();
  }

  goBack(): void {
    if (this.userId()) {
      this.closed.emit();
      return;
    }
    this.location.back();
  }

  /** Fetch user with sites from GET /api/users/:id */
  loadUser(id: string): void {
    this.loading.set(true);
    this.usersApi.get(id).subscribe({
      next: (data) => {
        this.user.set(data);
        this.refreshAvatarDisplayUrl(data as any);
        this.form.patchValue({
          site_ids: data.sites.map((s) => s.site_id),
        });
        this.profileForm.patchValue({
          first_name: data.first_name,
          last_name: data.last_name,
          email: data.email,
          role: (data.role as 'SITE_USER' | 'CORPORATE_USER') ?? 'SITE_USER',
          password: '',
        });
        // Keep one visible selector row at all times in Assigned sites.
        this.siteAccessRows.set([{ site_id: '', grade: 'level_0' }]);
        const rawPermissions: any = (data as any).permissions;
        if (rawPermissions && Array.isArray(rawPermissions.keys)) {
          const allowed = new Set(this.defaultPermissionKeysForRole(data.role, (data as any).level ?? null));
          this.globalPermissionKeys.set(rawPermissions.keys.map((k: any) => String(k)).filter((k: string) => allowed.has(k)));
        } else if (rawPermissions) {
          // Backward compatibility: keep existing matrix support for corporate defaults.
          this.permissions.set(rawPermissions);
          const keys: string[] = [];
          for (const [resource, actions] of Object.entries(rawPermissions as any)) {
            for (const [action, allowed] of Object.entries((actions as any) || {})) {
              if (allowed) keys.push(`${resource}.${action}`);
            }
          }
          this.globalPermissionKeys.set(keys);
        } else {
          this.globalPermissionKeys.set(this.defaultPermissionKeysForRole(data.role, (data as any).level ?? null));
        }
        // Safety net: users with no explicit stored keys inherit role defaults in app behavior.
        if (this.globalPermissionKeys().length === 0) {
          this.globalPermissionKeys.set(this.defaultPermissionKeysForRole(data.role, (data as any).level ?? null));
        }
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.message ?? this.translate.instant('COMMON.ERROR'));
        this.loading.set(false);
      },
    });
  }

  /** Fetch active sites for site assignment checkboxes */
  loadSites(): void {
    this.sitesApi.list(true).subscribe({
      next: (data) => this.sites.set(data),
    });
  }

  /** Toggle site in assignment form */
  toggleSite(siteId: string): void {
    const current = this.form.get('site_ids')?.value ?? [];
    const next = current.includes(siteId) ? current.filter((id) => id !== siteId) : [...current, siteId];
    this.form.patchValue({ site_ids: next });
  }

  /** Check if site is selected in assignment form */
  isSelected(siteId: string): boolean {
    return (this.form.get('site_ids')?.value ?? []).includes(siteId);
  }

  /** Save site assignment via POST /api/users/:id/sites */
  saveSites(): void {
    const u = this.user();
    if (!u) return;

    this.saving.set(true);
    this.errorMessage.set(null);
    const raw = this.form.getRawValue();
    const rows = this.siteAccessRows().filter((r) => !!r.site_id);
    const merged = new Map<string, { site_id: string; grade: 'level_0' | 'level_1' | 'level_2' | 'level_3' }>();
    for (const s of u.sites ?? []) {
      if (!s.site_id) continue;
      merged.set(s.site_id, {
        site_id: s.site_id,
        grade: ((s.grade as 'level_0' | 'level_1' | 'level_2' | 'level_3') || 'level_0'),
      });
    }
    for (const r of rows) merged.set(r.site_id, r);
    const payloadRows = Array.from(merged.values());
    this.usersApi.assignSites(u.id, {
      site_ids: payloadRows.map((r) => r.site_id),
      default_grade: raw.default_grade ?? undefined,
      site_accesses: payloadRows,
    }).subscribe({
      next: () => {
        this.loadUser(u.id);
        this.saving.set(false);
        this.successMessage.set(this.translate.instant('USER_DETAIL.MSG_ACCESS_UPDATED'));
        setTimeout(() => this.successMessage.set(null), 3000);
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.message ?? this.translate.instant('COMMON.ERROR'));
        this.saving.set(false);
      },
    });
  }

  addSiteAccessRow(): void {
    this.siteAccessRows.update((rows) => [...rows, { site_id: '', grade: 'level_0' }]);
  }

  removeSiteAccessRow(index: number): void {
    this.siteAccessRows.update((rows) => {
      const next = rows.filter((_, i) => i !== index);
      return next.length > 0 ? next : [{ site_id: '', grade: 'level_0' }];
    });
  }

  updateRowSite(index: number, site_id: string): void {
    this.siteAccessRows.update((rows) => rows.map((r, i) => i === index ? { ...r, site_id } : r));
  }

  updateRowGrade(index: number, grade: 'level_0' | 'level_1' | 'level_2' | 'level_3'): void {
    this.siteAccessRows.update((rows) => rows.map((r, i) => i === index ? { ...r, grade } : r));
  }

  availableSitesForRow(index: number): Site[] {
    const all = this.sites();
    const u = this.user();
    const rows = this.siteAccessRows();
    const currentRow = rows[index];
    const currentSiteId = currentRow?.site_id || '';

    const alreadyAssigned = new Set((u?.sites ?? []).map((s) => s.site_id).filter(Boolean) as string[]);
    const selectedInOtherRows = new Set(
      rows
        .filter((_, i) => i !== index)
        .map((r) => r.site_id)
        .filter((id) => !!id)
    );

    return all.filter((site) => {
      if (site.id === currentSiteId) return true;
      if (alreadyAssigned.has(site.id)) return false;
      if (selectedInOtherRows.has(site.id)) return false;
      return true;
    });
  }

  openRevokeSiteModal(site: { site_id: string; site_name: string | null }): void {
    this.revokingSite.set(site);
    this.showRevokeSiteModal.set(true);
  }

  closeRevokeSiteModal(): void {
    this.showRevokeSiteModal.set(false);
    this.revokingSite.set(null);
  }

  confirmRevokeSite(): void {
    const u = this.user();
    const target = this.revokingSite();
    if (!u || !target) return;
    this.saving.set(true);
    this.usersApi.revokeSiteAccess(u.id, target.site_id).subscribe({
      next: () => {
        this.loadUser(u.id);
        this.closeRevokeSiteModal();
        this.saving.set(false);
        this.successMessage.set(this.translate.instant('USER_DETAIL.MSG_SITE_REMOVED'));
        setTimeout(() => this.successMessage.set(null), 3000);
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.message ?? this.translate.instant('COMMON.ERROR'));
        this.saving.set(false);
      },
    });
  }

  saveProfile(): void {
    const u = this.user();
    if (!u) return;
    const raw = this.profileForm.getRawValue();
    const payload: any = {
      first_name: (raw.first_name || '').trim(),
      last_name: (raw.last_name || '').trim(),
      role: raw.role || 'SITE_USER',
    };
    if ((raw.password || '').trim()) payload.password = raw.password;
    this.actionLoading.set('profile');
    this.usersApi.update(u.id, payload).subscribe({
      next: (updated) => {
        this.user.set({ ...u, ...updated });
        this.refreshAvatarDisplayUrl({ ...u, ...updated } as any);
        this.successMessage.set(this.translate.instant('USER_DETAIL.MSG_PROFILE_UPDATED'));
        this.actionLoading.set(null);
        this.profileForm.patchValue({ password: '' });
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.message ?? this.translate.instant('COMMON.ERROR'));
        this.actionLoading.set(null);
      },
    });
  }

  saveAll(): void {
    const u = this.user();
    if (!u) return;
    const rawProfile = this.profileForm.getRawValue();
    const profilePayload: any = {
      first_name: (rawProfile.first_name || '').trim(),
      last_name: (rawProfile.last_name || '').trim(),
      role: rawProfile.role || 'SITE_USER',
    };
    if ((rawProfile.password || '').trim()) profilePayload.password = rawProfile.password;

    this.actionLoading.set('profile');
    this.errorMessage.set(null);
    this.usersApi.update(u.id, profilePayload).subscribe({
      next: (updated) => {
        const targetRole = (profilePayload.role as 'SITE_USER' | 'CORPORATE_USER') ?? 'SITE_USER';
        if (targetRole !== 'SITE_USER') {
          this.toast.emit({ type: 'success', message: this.translate.instant('USER_DETAIL.MSG_PROFILE_UPDATED') });
          this.actionLoading.set(null);
          this.goBack();
          return;
        }

        this.saving.set(true);
        const raw = this.form.getRawValue();
        const rows = this.siteAccessRows().filter((r) => !!r.site_id);
        const merged = new Map<string, { site_id: string; grade: 'level_0' | 'level_1' | 'level_2' | 'level_3' }>();
        for (const s of (u.sites ?? [])) {
          if (!s.site_id) continue;
          merged.set(s.site_id, {
            site_id: s.site_id,
            grade: ((s.grade as 'level_0' | 'level_1' | 'level_2' | 'level_3') || 'level_0'),
          });
        }
        for (const r of rows) merged.set(r.site_id, r);
        const payloadRows = Array.from(merged.values());
        this.usersApi.assignSites(u.id, {
          site_ids: payloadRows.map((r) => r.site_id),
          default_grade: raw.default_grade ?? undefined,
          site_accesses: payloadRows,
        }).subscribe({
          next: () => {
            this.toast.emit({ type: 'success', message: this.translate.instant('USER_DETAIL.MSG_PROFILE_UPDATED') });
            this.actionLoading.set(null);
            this.saving.set(false);
            this.goBack();
          },
          error: (err) => {
            const msg = err?.error?.message ?? this.translate.instant('COMMON.ERROR');
            this.errorMessage.set(msg);
            this.toast.emit({ type: 'error', message: msg });
            this.actionLoading.set(null);
            this.saving.set(false);
            this.user.set({ ...u, ...updated });
          },
        });
      },
      error: (err) => {
        const msg = err?.error?.message ?? this.translate.instant('COMMON.ERROR');
        this.errorMessage.set(msg);
        this.toast.emit({ type: 'error', message: msg });
        this.actionLoading.set(null);
      },
    });
  }

  /** Activate/deactivate user */
  toggleActive(): void {
    const u = this.user();
    if (!u || this.actionLoading()) return;

    this.actionLoading.set('toggle');
    this.errorMessage.set(null);
    this.usersApi.update(u.id, { is_active: !u.is_active }).subscribe({
      next: (updated) => {
        this.user.set({ ...u, ...updated });
        this.successMessage.set(
          this.translate.instant(updated.is_active ? 'USER_DETAIL.MSG_USER_ACTIVATED' : 'USER_DETAIL.MSG_USER_DEACTIVATED')
        );
        this.actionLoading.set(null);
        setTimeout(() => this.successMessage.set(null), 3000);
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.message ?? this.translate.instant('COMMON.ERROR'));
        this.actionLoading.set(null);
      },
    });
  }

  /** Generate new password, show in modal */
  generatePassword(): void {
    const u = this.user();
    if (!u || this.actionLoading()) return;

    this.actionLoading.set('password');
    this.errorMessage.set(null);
    this.usersApi.resetPassword(u.id).subscribe({
      next: (res) => {
        this.generatedPassword.set(res.password);
        this.showPasswordModal.set(true);
        this.actionLoading.set(null);
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.message ?? this.translate.instant('COMMON.ERROR'));
        this.actionLoading.set(null);
      },
    });
  }

  /** Close password modal and clear generated password */
  closePasswordModal(): void {
    this.showPasswordModal.set(false);
    this.generatedPassword.set(null);
  }

  /** Copy generated password to clipboard */
  copyPassword(): void {
    const p = this.generatedPassword();
    if (p && navigator.clipboard) {
      navigator.clipboard.writeText(p);
    }
  }

  /** Map role to display label */
  roleLabel(role: string): string {
    return role === 'CORPORATE_USER'
      ? this.translate.instant('USER_DETAIL.ROLE_CORPORATE')
      : this.translate.instant('USER_DETAIL.ROLE_SITE');
  }

  /** Map grade to display label */
  gradeLabel(grade: string | null | undefined): string {
    if (!grade) return '—';
    if (grade === 'level_3') return this.translate.instant('USER_DETAIL.GRADE_LEVEL_3');
    if (grade === 'level_2') return this.translate.instant('USER_DETAIL.GRADE_LEVEL_2');
    if (grade === 'level_1') return this.translate.instant('USER_DETAIL.GRADE_LEVEL_1');
    if (grade === 'level_0') return this.translate.instant('USER_DETAIL.GRADE_LEVEL_0');
    return grade;
  }

  togglePermission(resource: 'plan' | 'activity', action: 'create' | 'read' | 'update' | 'delete' | 'approve' | 'reject'): void {
    const current = this.permissions();
    this.permissions.set({
      ...current,
      [resource]: {
        ...current[resource],
        [action]: !current[resource][action],
      },
    });
  }

  savePermissions(): void {
    const u = this.user();
    if (!u) return;
    this.permissionSaving.set(true);
    this.usersApi.update(u.id, { permissions: { keys: this.globalPermissionKeys() } as any }).subscribe({
      next: (updated) => {
        this.user.set({ ...u, ...updated });
        this.successMessage.set(this.translate.instant('USER_DETAIL.MSG_PERMISSIONS_UPDATED'));
        this.permissionSaving.set(false);
        this.showGlobalPermissionsModal.set(false);
        setTimeout(() => this.successMessage.set(null), 3000);
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.message ?? this.translate.instant('COMMON.ERROR'));
        this.permissionSaving.set(false);
      },
    });
  }

  hasGlobalPermission(key: string): boolean {
    return this.globalPermissionKeys().includes(key);
  }

  toggleGlobalPermission(key: string): void {
    const current = this.globalPermissionKeys();
    this.globalPermissionKeys.set(
      current.includes(key) ? current.filter((k) => k !== key) : [...current, key]
    );
  }

  openGlobalPermissionsModal(): void {
    this.showGlobalPermissionsModal.set(true);
  }

  closeGlobalPermissionsModal(): void {
    this.showGlobalPermissionsModal.set(false);
  }

  userInitials(): string {
    const u = this.user();
    if (!u) return '?';
    const fn = (u.first_name ?? '').trim();
    const ln = (u.last_name ?? '').trim();
    if (fn && ln) return (fn[0] + ln[0]).toUpperCase();
    if (fn) return fn.slice(0, 2).toUpperCase();
    if (ln) return ln.slice(0, 2).toUpperCase();
    return '?';
  }

  private refreshAvatarDisplayUrl(userLike: { avatar_url?: string | null } | null | undefined): void {
    const url = (userLike?.avatar_url ?? '').trim();
    const prev = this.avatarDisplayUrl();
    if (prev) {
      try { URL.revokeObjectURL(prev); } catch {}
    }
    if (!url) {
      this.avatarDisplayUrl.set(null);
      return;
    }
    const sep = url.includes('?') ? '&' : '?';
    this.http.get(`${url}${sep}t=${Date.now()}`, { responseType: 'blob' }).subscribe({
      next: (blob) => this.avatarDisplayUrl.set(URL.createObjectURL(blob)),
      error: () => this.avatarDisplayUrl.set(null),
    });
  }

  targetRole(): 'SITE_USER' | 'CORPORATE_USER' {
    const formRole = this.profileForm.get('role')?.value;
    if (formRole === 'CORPORATE_USER') return 'CORPORATE_USER';
    if (formRole === 'SITE_USER') return 'SITE_USER';
    return this.user()?.role === 'CORPORATE_USER' ? 'CORPORATE_USER' : 'SITE_USER';
  }

  visiblePermissionCategories() {
    const allowed = new Set(this.rolePermissionCategoryKeys[this.targetRole()]);
    const allowedKeys = new Set(this.defaultPermissionKeysForRole(this.targetRole(), this.currentSiteUserLevel()));
    return this.sitePermissionCategories
      .filter((cat) => allowed.has(cat.key))
      .map((cat) => ({ ...cat, items: cat.items.filter((it) => allowedKeys.has(it.key)) }))
      .filter((cat) => cat.items.length > 0);
  }

  private currentSiteUserLevel(): string | null {
    const sites = this.user()?.sites ?? [];
    const grades = sites.map((s) => String(s.grade ?? '').toLowerCase());
    if (grades.includes('level_3')) return 'level_3';
    if (grades.includes('level_2')) return 'level_2';
    if (grades.includes('level_1')) return 'level_1';
    if (grades.some((g) => g === '' || g === 'level_0')) return 'level_0';
    return null;
  }

  private defaultPermissionKeysForRole(role?: string | null, level?: string | null): string[] {
    const normalizedRole: 'SITE_USER' | 'CORPORATE_USER' =
      (role || '').toUpperCase() === 'CORPORATE_USER' ? 'CORPORATE_USER' : 'SITE_USER';
    if (normalizedRole === 'SITE_USER') {
      if (level === 'level_1' || level === 'level_2' || level === 'level_3') {
        return Array.from(new Set(this.siteUserValidatorKeys));
      }
      return Array.from(new Set(this.siteUserCreatorKeys));
    }
    const allowedCats = new Set(this.rolePermissionCategoryKeys[normalizedRole]);
    const keys = this.sitePermissionCategories
      .filter((cat) => allowedCats.has(cat.key))
      .flatMap((cat) => cat.items.map((item) => item.key));
    return Array.from(new Set(keys));
  }
}
