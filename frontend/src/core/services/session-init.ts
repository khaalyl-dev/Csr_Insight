import { inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AuthApi } from '@features/user-management/login/auth-api';
import { AuthStore, mapBackendRole } from './auth-store';
import { applyAvatarUrlToStore } from './auth-avatar.util';
import { firstValueFrom } from 'rxjs';
import { catchError, of, tap } from 'rxjs';

/**
 * Validates the stored session on app init.
 * If token exists but GET /api/auth/me returns 401, clears auth.
 */
export function initSession(): () => Promise<void> {
  const authStore = inject(AuthStore);
  const authApi = inject(AuthApi);
  const http = inject(HttpClient);
  return () => {
    if (!authStore.token()) {
      return Promise.resolve();
    }
    return firstValueFrom(
      authApi.getMe().pipe(
        tap((res) => {
          if (res) {
            authStore.patchUser({
              email: res.email,
              role: mapBackendRole(res.role),
              level: res.level ?? null,
              first_name: res.first_name ?? undefined,
              last_name: res.last_name ?? undefined,
              permissions: res.permissions ?? null,
            });
            applyAvatarUrlToStore(authStore, http, res.avatar_url);
          }
        }),
        catchError(() => {
          authStore.clearAuth();
          return of(null);
        })
      )
    ).then(() => undefined);
  };
}
