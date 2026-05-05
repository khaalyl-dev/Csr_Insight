import { inject } from '@angular/core';
import { Router, type CanActivateFn } from '@angular/router';
import { AuthStore } from '../services/auth-store';

export const authGuard: CanActivateFn = () => {
  const authStore = inject(AuthStore);
  const router = inject(Router);

  if (authStore.isAuthenticated()) {
    return true;
  }

  return router.createUrlTree(['/login']);
};

export const roleGuard = (allowedRoles: ('site' | 'corporate')[]): CanActivateFn => {
  return () => {
    const authStore = inject(AuthStore);
    const router = inject(Router);

    if (!authStore.isAuthenticated()) {
      return router.createUrlTree(['/login']);
    }

    const userRole = authStore.userRole();

    if (userRole && allowedRoles.includes(userRole)) {
      return true;
    }

    const defaultRoute = userRole === 'site' ? '/dashboard/site' : '/dashboard/corporate';
    return router.createUrlTree([defaultRoute]);
  };
};

export const permissionGuard = (requiredAny: string[]): CanActivateFn => {
  return () => {
    const authStore = inject(AuthStore);
    const router = inject(Router);

    if (!authStore.isAuthenticated()) {
      return router.createUrlTree(['/login']);
    }

    if (!requiredAny?.length || authStore.hasAnyPermission(requiredAny)) {
      return true;
    }

    const userRole = authStore.userRole();
    const defaultRoute = userRole === 'site' ? '/dashboard/site' : '/dashboard/corporate';
    return router.createUrlTree([defaultRoute]);
  };
};

export const validatorLevelGuard: CanActivateFn = () => {
  const authStore = inject(AuthStore);
  const router = inject(Router);
  if (!authStore.isAuthenticated()) {
    return router.createUrlTree(['/login']);
  }
  const role = authStore.userRole();
  if (role === 'corporate') return true;
  if (authStore.isValidatorLevel()) return true;
  return router.createUrlTree(['/dashboard/site']);
};
