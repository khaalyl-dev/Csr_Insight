import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap, catchError } from 'rxjs/operators';
import { throwError } from 'rxjs';
import { AuthApi } from '@features/user-management/login/auth-api';
import { AuthStore, mapBackendRole } from './auth-store';
import { applyAvatarUrlToStore } from './auth-avatar.util';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private authStore = inject(AuthStore);
  private router = inject(Router);
  private authApi = inject(AuthApi);
  private http = inject(HttpClient);

  login(email: string, password: string, remember = false) {
    return this.authApi.login(email, password).pipe(
      tap(res => {
        const user = {
          email: res.email,
          role: mapBackendRole(res.role),
          level: res.level ?? null,
          first_name: res.first_name ?? undefined,
          last_name: res.last_name ?? undefined,
          permissions: res.permissions ?? null,
        };

        this.authStore.setAuth(res.token, user, remember);
        applyAvatarUrlToStore(this.authStore, this.http, res.avatar_url);

        const defaultRoute = user.role === 'site' ? '/dashboard/site' : '/dashboard/corporate';
        this.router.navigate([defaultRoute]);
      }),
      catchError(error => {
        return throwError(() => error);
      })
    );
  }

  logout() {
    const token = this.authStore.token();
    if (!token) {
      this.authStore.clearAuth();
      this.router.navigate(['/login']);
      return;
    }

    this.authApi.logout().subscribe({
      next: () => {
        this.authStore.clearAuth();
        this.router.navigate(['/login']);
      },
      error: () => {
        this.authStore.clearAuth();
        this.router.navigate(['/login']);
      }
    });
  }
}
