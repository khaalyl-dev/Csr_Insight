import { Component, inject, computed, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { AuthStore } from '@core/services/auth-store';
import { AuthService } from '@core/services/auth.service';
import { SidebarService } from '@core/services/sidebar.service';
import { navItems, type NavSection, type NavItem } from './nav-config';
import { FontAwesomeModule } from '@fortawesome/angular-fontawesome';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterModule, FontAwesomeModule, TranslateModule],
  templateUrl: './sidebar.html',
  styleUrls: ['./sidebar.css']
})
export class Sidebar implements OnDestroy {
  private authStore = inject(AuthStore);
  private authService = inject(AuthService);
  private router = inject(Router);
  private translate = inject(TranslateService);
  sidebarService = inject(SidebarService);

  isCollapsed = this.sidebarService.isCollapsed;
  avatarDisplayUrl = this.authStore.avatarDisplayUrl;

  constructor() {
    this.sidebarService.initFromStorage();
  }

  ngOnDestroy(): void {}

  filteredNavItems = computed(() => {
    const role = this.authStore.userRole();
    if (!role) return [];

    return navItems
      .filter(section => section.roles.includes(role))
      .map(section => ({
        ...section,
        items: section.items.filter((item) =>
          item.roles.includes(role) &&
          (!item.requiresValidatorLevel || role === 'corporate' || this.authStore.isValidatorLevel()) &&
          (!item.requiresCreatorLevel || role === 'corporate' || this.authStore.isCreatorLevel()) &&
          (item.permissionAny == null || this.authStore.hasAnyPermission(item.permissionAny))
        )
      }))
      .filter(section => section.items.length > 0);
  });

  isAuthenticated = this.authStore.isAuthenticated;
  user = this.authStore.user;

  toggleSidebar(): void {
    this.sidebarService.toggle();
  }

  trackBySection(index: number, section: NavSection) {
    return section.sectionKey;
  }

  trackByItem(index: number, item: NavItem) {
    return item.path;
  }

  userInitials(): string {
    const u = this.authStore.user();
    if (!u?.email) return '?';
    const fn = (u.first_name ?? '').trim();
    const ln = (u.last_name ?? '').trim();
    if (fn && ln) return (fn[0] + ln[0]).toUpperCase();
    if (fn.length >= 2) return fn.slice(0, 2).toUpperCase();
    if (fn) return fn.slice(0, 2).toUpperCase();
    if (ln) return ln.slice(0, 2).toUpperCase();
    const local = u.email.split('@')[0] || '';
    return local.slice(0, 2).toUpperCase() || '?';
  }

  /** First + last name when available; otherwise legacy role label (Site / Corporate user). */
  userDisplayName(): string {
    const u = this.authStore.user();
    if (!u) return '';
    const parts = [(u.first_name ?? '').trim(), (u.last_name ?? '').trim()].filter(Boolean);
    if (parts.length) return parts.join(' ');
    return this.roleLabel(u.role);
  }

  private roleLabel(role?: 'site' | 'corporate' | null): string {
    if (!role) return '';
    return role === 'corporate'
      ? this.translate.instant('PROFILE_SETTINGS.ACCOUNT.CORPORATE_USER')
      : this.translate.instant('PROFILE_SETTINGS.ACCOUNT.SITE_USER');
  }

  logout() {
    this.authService.logout();
  }
}
