import { Injectable, signal, computed } from '@angular/core';

const TOKEN_KEY = 'auth.token';
const USER_KEY = 'auth.user';

export interface User {
  email: string;
  role: 'site' | 'corporate';
  level?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  permissions?: { keys?: string[] } | null;
}

/** Normalize SITE_USER / CORPORATE_USER (or legacy strings) to sidebar guards. */
export function mapBackendRole(role: string): 'site' | 'corporate' {
  return role === 'CORPORATE_USER' || role === 'corporate' ? 'corporate' : 'site';
}

type StorageLike = Storage | null;

function safeStorage(storage: StorageLike): Storage | null {
  try {
    return typeof window !== 'undefined' ? storage : null;
  } catch {
    return null;
  }
}

@Injectable({ providedIn: 'root' })
export class AuthStore {
  private getStorage(remember: boolean): Storage | null {
    const s = safeStorage(window.sessionStorage);
    const l = safeStorage(window.localStorage);
    return remember && l ? l : s;
  }

  private static readonly initialToken = (() => {
    try {
      if (typeof window === 'undefined') return null;
      return (
        window.sessionStorage.getItem(TOKEN_KEY) ??
        window.localStorage.getItem(TOKEN_KEY)
      );
    } catch {
      return null;
    }
  })();

  private static readonly initialUser = (() => {
    try {
      if (typeof window === 'undefined') return null;
      const stored =
        window.sessionStorage.getItem(USER_KEY) ??
        window.localStorage.getItem(USER_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  })();

  readonly token = signal<string | null>(AuthStore.initialToken);
  readonly user = signal<User | null>(AuthStore.initialUser);
  /** Display-ready avatar URL (blob URL) – set by profile settings after successful fetch. */
  readonly avatarDisplayUrl = signal<string | null>(null);
  readonly isAuthenticated = computed(() => !!this.token());
  readonly userRole = computed(() => this.user()?.role ?? null);

  setAvatarDisplayUrl(url: string | null): void {
    const prev = this.avatarDisplayUrl();
    if (prev) URL.revokeObjectURL(prev);
    this.avatarDisplayUrl.set(url);
  }

  setAuth(token: string, user: User, remember = true): void {
    this.token.set(token);
    this.user.set(user);
    this.clearStorage();
    const storage = this.getStorage(remember);
    if (storage) {
      try {
        storage.setItem(TOKEN_KEY, token);
        storage.setItem(USER_KEY, JSON.stringify(user));
      } catch {}
    }
  }

  /** Merge into the current user and persist wherever `auth.user` is already stored. */
  patchUser(updates: Partial<Pick<User, 'email' | 'role' | 'level' | 'first_name' | 'last_name' | 'permissions'>>): void {
    const current = this.user();
    if (!current) return;
    const next: User = { ...current, ...updates };
    this.user.set(next);
    try {
      if (typeof window === 'undefined') return;
      const json = JSON.stringify(next);
      if (window.sessionStorage.getItem(USER_KEY)) {
        window.sessionStorage.setItem(USER_KEY, json);
      }
      if (window.localStorage.getItem(USER_KEY)) {
        window.localStorage.setItem(USER_KEY, json);
      }
    } catch {}
  }

  permissionKeys(): string[] {
    const keys = this.user()?.permissions?.keys;
    return Array.isArray(keys) ? keys : [];
  }

  hasPermission(key: string): boolean {
    const keys = this.permissionKeys();
    if (!keys.length) return true;
    if (keys.includes(key)) return true;
    const [resource, action] = key.split('.');
    if ((action === 'approve' || action === 'reject') && keys.includes(`${resource}.validate`)) {
      return true;
    }
    return false;
  }

  hasAnyPermission(keys: string[]): boolean {
    return keys.some((k) => this.hasPermission(k));
  }

  isValidatorLevel(): boolean {
    const lvl = (this.user()?.level || '').toLowerCase();
    return lvl === 'level_1' || lvl === 'level_2' || lvl === 'level_3';
  }

  isCreatorLevel(): boolean {
    const lvl = (this.user()?.level || '').toLowerCase();
    return lvl === '' || lvl === 'level_0';
  }

  clearAuth(): void {
    const prev = this.avatarDisplayUrl();
    if (prev) URL.revokeObjectURL(prev);
    this.avatarDisplayUrl.set(null);
    this.token.set(null);
    this.user.set(null);
    this.clearStorage();
  }

  private clearStorage(): void {
    try {
      if (typeof window === 'undefined') return;
      window.sessionStorage.removeItem(TOKEN_KEY);
      window.sessionStorage.removeItem(USER_KEY);
      window.localStorage.removeItem(TOKEN_KEY);
      window.localStorage.removeItem(USER_KEY);
    } catch {}
  }
}
