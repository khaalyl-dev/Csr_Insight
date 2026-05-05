/**
 * UsersListComponent - Page liste des utilisateurs (corporate only).
 * Route: /admin/users
 * Features: create user, list users table, toggle active, generate password, assign sites on create.
 */
import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { FontAwesomeModule } from '@fortawesome/angular-fontawesome';
import { faUserPlus, faKey, faBan, faCheck, faBuilding } from '@fortawesome/free-solid-svg-icons';
import { UsersApi, type User, type CreateUserPayload } from '../api/users-api';
import { SitesApi, type Site } from '@features/site-management/api/sites-api';
import { UserDetailComponent } from '../user-detail/user-detail';

@Component({
  selector: 'app-users-list',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FontAwesomeModule, TranslateModule, UserDetailComponent],
  templateUrl: './users-list.html',
})
export class UsersListComponent implements OnInit {
  private readonly usersApi = inject(UsersApi);
  private readonly sitesApi = inject(SitesApi);
  private readonly fb = inject(FormBuilder);
  private readonly translate = inject(TranslateService);

  protected readonly faUserPlus = faUserPlus;
  protected readonly faKey = faKey;
  protected readonly faBan = faBan;
  protected readonly faCheck = faCheck;
  protected readonly faBuilding = faBuilding;

  users = signal<User[]>([]);
  sites = signal<Site[]>([]);
  loading = signal(false);
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);
  showCreateForm = signal(false);
  showPasswordModal = signal(false);
  showPermissionsModal = signal(false);
  showUserDetailModal = signal(false);
  generatedPassword = signal<string | null>(null);
  userForPassword = signal<string | null>(null);
  selectedUserForPermissions = signal<User | null>(null);
  selectedUserId = signal<string | null>(null);
  permissionSaving = signal(false);
  permissionKeysDraft = signal<string[]>([]);
  actionLoading = signal<string | null>(null);
  readonly permissionCategories = [
    {
      key: 'dashboard',
      labelKey: 'USER_DETAIL.CAT.DASHBOARD',
      items: [{ key: 'dashboard.read', labelKey: 'USER_DETAIL.PERM.DASHBOARD_READ_DETAIL' }],
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
      items: [{ key: 'task.read', labelKey: 'USER_DETAIL.PERM.TASK_READ' }],
    },
  ] as const;
  readonly rolePermissionCategoryKeys: Record<'SITE_USER' | 'CORPORATE_USER', string[]> = {
    SITE_USER: ['dashboard', 'plan', 'activity', 'realized_activity', 'document', 'change_request', 'task'],
    CORPORATE_USER: ['dashboard', 'plan', 'activity', 'realized_activity', 'document', 'change_request', 'site', 'category', 'user', 'audit_log', 'notification', 'task'],
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

  createForm = this.fb.nonNullable.group({
    first_name: ['', Validators.required],
    last_name: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(6)]],
    role: ['SITE_USER' as 'SITE_USER' | 'CORPORATE_USER'],
    site_ids: [[] as string[]],
    default_grade: ['level_0' as 'level_0' | 'level_1' | 'level_2' | 'level_3'],
  });

  ngOnInit(): void {
    this.loadUsers();
    this.loadSites();
  }

  /** Fetch all users from GET /api/users */
  loadUsers(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.usersApi.list().subscribe({
      next: (data) => {
        this.users.set(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.message ?? this.translate.instant('USERS.LOAD_ERROR'));
        this.loading.set(false);
      },
    });
  }

  /** Fetch active sites for create form */
  loadSites(): void {
    this.sitesApi.list(true).subscribe({
      next: (data) => this.sites.set(data),
      error: () => {},
    });
  }

  /** Show/hide create user form, reset form when hiding */
  toggleCreateForm(): void {
    this.showCreateForm.update((v) => !v);
    if (!this.showCreateForm()) {
      this.createForm.reset({
        first_name: '',
        last_name: '',
        email: '',
        password: '',
        role: 'SITE_USER',
        site_ids: [],
        default_grade: 'level_0',
      });
      this.errorMessage.set(null);
    }
  }

  /** Submit create form: create user, optionally assign sites */
  onSubmitCreate(): void {
    if (this.createForm.invalid) return;

    this.errorMessage.set(null);
    this.successMessage.set(null);
    const raw = this.createForm.getRawValue();
    const payload: CreateUserPayload = {
      first_name: raw.first_name,
      last_name: raw.last_name,
      email: raw.email,
      password: raw.password,
      role: raw.role,
    };

    this.usersApi.create(payload).subscribe({
      next: (user) => {
        this.users.update((list) => [...list, user]);
        this.toggleCreateForm();
        this.successMessage.set(this.translate.instant('USERS.USER_CREATED_SUCCESS', { email: user.email }));

        if (raw.role === 'SITE_USER' && raw.site_ids.length > 0) {
          this.usersApi.assignSites(user.id, {
            site_ids: raw.site_ids,
            default_grade: raw.default_grade ?? undefined,
          }).subscribe({
            next: () => this.loadUsers(),
          });
        }
        setTimeout(() => this.successMessage.set(null), 4000);
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.message ?? this.translate.instant('USERS.CREATE_ERROR'));
      },
    });
  }

  /** Toggle site checkbox in create form */
  toggleSiteSelection(siteId: string): void {
    const siteIds = this.createForm.get('site_ids')?.value ?? [];
    const idx = siteIds.indexOf(siteId);
    const next = idx >= 0 ? siteIds.filter((_, i) => i !== idx) : [...siteIds, siteId];
    this.createForm.patchValue({ site_ids: next });
  }

  /** Check if site is selected in create form */
  isSiteSelected(siteId: string): boolean {
    return (this.createForm.get('site_ids')?.value ?? []).includes(siteId);
  }

  /** Activate/deactivate user via PATCH /api/users/:id */
  toggleActive(user: User): void {
    if (this.actionLoading()) return;
    this.actionLoading.set(user.id);
    this.errorMessage.set(null);
    this.usersApi.update(user.id, { is_active: !user.is_active }).subscribe({
      next: (updated) => {
        this.users.update((list) =>
          list.map((u) => (u.id === updated.id ? updated : u))
        );
        this.successMessage.set(
          updated.is_active ? this.translate.instant('USERS.USER_ACTIVATED') : this.translate.instant('USERS.USER_DEACTIVATED')
        );
        this.actionLoading.set(null);
        setTimeout(() => this.successMessage.set(null), 3000);
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.message ?? this.translate.instant('USERS.ERROR_GENERIC'));
        this.actionLoading.set(null);
      },
    });
  }

  /** Generate new password for user, show in modal */
  generatePassword(user: User): void {
    if (this.actionLoading()) return;
    this.actionLoading.set(user.id);
    this.errorMessage.set(null);
    this.usersApi.resetPassword(user.id).subscribe({
      next: (res) => {
        this.generatedPassword.set(res.password);
        this.userForPassword.set(`${user.first_name} ${user.last_name} (${user.email})`);
        this.showPasswordModal.set(true);
        this.actionLoading.set(null);
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.message ?? this.translate.instant('USERS.ERROR_GENERIC'));
        this.actionLoading.set(null);
      },
    });
  }

  /** Close password modal and clear state */
  closePasswordModal(): void {
    this.showPasswordModal.set(false);
    this.generatedPassword.set(null);
    this.userForPassword.set(null);
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
      ? this.translate.instant('USERS.ROLE_CORPORATE')
      : this.translate.instant('USERS.ROLE_SITE');
  }

  /** Map level to display label */
  levelLabel(level: string | null | undefined): string {
    if (!level) return this.translate.instant('USERS.LEVEL_NA');
    if (level === 'level_3') return this.translate.instant('USERS.LEVEL_3');
    if (level === 'level_2') return this.translate.instant('USERS.LEVEL_2');
    if (level === 'level_1') return this.translate.instant('USERS.LEVEL_1');
    if (level === 'level_0') return this.translate.instant('USERS.LEVEL_0');
    return level;
  }

  openPermissionsModal(user: User): void {
    this.selectedUserForPermissions.set(user);
    const raw: any = user.permissions;
    if (raw && Array.isArray(raw.keys)) {
      const allowed = new Set(this.defaultPermissionKeysForRole(user.role, user.level));
      this.permissionKeysDraft.set(raw.keys.map((k: any) => String(k)).filter((k: string) => allowed.has(k)));
    } else {
      this.permissionKeysDraft.set(this.defaultPermissionKeysForRole(user.role, user.level));
    }
    this.showPermissionsModal.set(true);
  }

  openUserDetailModal(user: User): void {
    this.selectedUserId.set(user.id);
    this.showUserDetailModal.set(true);
  }

  closeUserDetailModal(refresh = true): void {
    this.showUserDetailModal.set(false);
    this.selectedUserId.set(null);
    if (refresh) {
      this.loadUsers();
    }
  }

  onUserDetailToast(event: { type: 'success' | 'error'; message: string }): void {
    if (event.type === 'success') {
      this.successMessage.set(event.message);
      this.errorMessage.set(null);
      setTimeout(() => this.successMessage.set(null), 3500);
      return;
    }
    this.errorMessage.set(event.message);
    this.successMessage.set(null);
    setTimeout(() => this.errorMessage.set(null), 5000);
  }

  closePermissionsModal(): void {
    this.showPermissionsModal.set(false);
    this.selectedUserForPermissions.set(null);
    this.permissionKeysDraft.set([]);
  }

  hasDraftPermission(key: string): boolean {
    return this.permissionKeysDraft().includes(key);
  }

  toggleDraftPermission(key: string): void {
    const current = this.permissionKeysDraft();
    this.permissionKeysDraft.set(current.includes(key) ? current.filter((k) => k !== key) : [...current, key]);
  }

  savePermissionsModal(): void {
    const u = this.selectedUserForPermissions();
    if (!u) return;
    this.permissionSaving.set(true);
    this.usersApi.update(u.id, { permissions: { keys: this.permissionKeysDraft() } as any }).subscribe({
      next: (updated) => {
        this.users.update((list) => list.map((row) => (row.id === updated.id ? { ...row, ...updated } : row)));
        this.permissionSaving.set(false);
        this.closePermissionsModal();
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.message ?? this.translate.instant('USERS.ERROR_GENERIC'));
        this.permissionSaving.set(false);
      },
    });
  }

  visiblePermissionCategoriesForModal() {
    const user = this.selectedUserForPermissions();
    const role = (((user?.role) || '').toUpperCase() === 'CORPORATE_USER')
      ? 'CORPORATE_USER'
      : 'SITE_USER';
    const allowed = new Set(this.rolePermissionCategoryKeys[role]);
    const allowedKeys = new Set(this.defaultPermissionKeysForRole(user?.role, user?.level));
    return this.permissionCategories
      .filter((cat) => allowed.has(cat.key))
      .map((cat) => ({ ...cat, items: cat.items.filter((it) => allowedKeys.has(it.key)) }))
      .filter((cat) => cat.items.length > 0);
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
    const keys = this.permissionCategories
      .filter((cat) => allowedCats.has(cat.key))
      .flatMap((cat) => cat.items.map((item) => item.key));
    return Array.from(new Set(keys));
  }
}
