import { Component, inject, signal, OnInit, OnDestroy, computed, effect, viewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, RouterOutlet, Router, NavigationEnd } from '@angular/router';
import { Location } from '@angular/common';
import { filter } from 'rxjs/operators';
import { Sidebar } from '@shared/components/sidebar/sidebar';
import { AuthStore } from '@core/services/auth-store';
import { BreadcrumbService } from '@core/services/breadcrumb.service';
import { SidebarService } from '@core/services/sidebar.service';
import { ThemeService } from '@core/services/theme.service';
import { NotificationBellComponent } from '@features/notification-management/notification-bell/notification-bell';
import { UserTasksBellComponent } from '@features/task-management/user-tasks-bell/user-tasks-bell';
import { ChatbotWidgetComponent } from '@shared/components/chatbot-widget/chatbot-widget';
import { I18nService } from '@core/services/i18n.service';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { NotificationSocketService } from '@core/services/notification-socket.service';

/** Segment labels for breadcrumb (path segment -> display label). */
const SEGMENT_LABELS: Record<string, string> = {
  dashboard: 'BREADCRUMB.DASHBOARD',
  'csr-plans': 'BREADCRUMB.CSR_PLANS',
  create: 'BREADCRUMB.CREATE',
  'annual-plans': 'BREADCRUMB.ANNUAL_PLANS',
  validation: 'BREADCRUMB.VALIDATION',
  'planned-activities': 'BREADCRUMB.PLANNED_ACTIVITIES',
  'planned-activity': 'BREADCRUMB.PLANNED_ACTIVITY',
  'realized-csr': 'BREADCRUMB.REALIZED_ACTIVITIES',
  sites: 'BREADCRUMB.SITES',
  categories: 'BREADCRUMB.CATEGORIES',
  admin: 'BREADCRUMB.ADMIN',
  users: 'BREADCRUMB.USERS',
  account: 'BREADCRUMB.ACCOUNT',
  profile: 'BREADCRUMB.PROFILE',
  documents: 'BREADCRUMB.DOCUMENTS',
  changes: 'BREADCRUMB.CHANGES',
  pending: 'BREADCRUMB.PENDING',
  history: 'BREADCRUMB.HISTORY',
  edit: 'BREADCRUMB.EDIT',
  audit: 'BREADCRUMB.AUDIT_LOG',
};

@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [CommonModule, RouterModule, Sidebar, UserTasksBellComponent, NotificationBellComponent, ChatbotWidgetComponent, TranslateModule],
  templateUrl: './main-layout.html'
})
export class MainLayout implements OnInit, OnDestroy {
  private authStore = inject(AuthStore);
  private notificationSocket = inject(NotificationSocketService);
  private router = inject(Router);
  private location = inject(Location);
  private breadcrumbService = inject(BreadcrumbService);
  private i18n = inject(I18nService);
  private translate = inject(TranslateService);
  theme = inject(ThemeService);
  sidebarService = inject(SidebarService);

  /** Scroll container for routed pages (`overflow-auto`); not the window. */
  private mainScroll = viewChild<ElementRef<HTMLElement>>('mainScroll');

  isAuthenticated = this.authStore.isAuthenticated;
  /** Base breadcrumb from URL (without context) */
  private baseBreadcrumb = signal<string[]>([]);

  /** Final breadcrumb: base + optional context (e.g. site name) before "Détail" */
  breadcrumb = computed(() => {
    const base = this.baseBreadcrumb();
    const context = this.breadcrumbService.getContext()();
    if (!context.length) return base;
    const detailLabel = this.i18n.t('BREADCRUMB.DETAIL');
    const editLabel = this.i18n.t('BREADCRUMB.EDIT');
    const detailIndex = base.indexOf(detailLabel);
    if (detailIndex === -1) return base;
    const isEditPage = base[detailIndex + 1] === editLabel;
    const replacement = isEditPage ? [...context] : [...context, detailLabel];
    return [...base.slice(0, detailIndex), ...replacement, ...base.slice(detailIndex + 1)];
  });

  private sub: ReturnType<typeof this.router.events.subscribe> | null = null;
  private langSub: ReturnType<typeof this.translate.onLangChange.subscribe> | null = null;

  /** Brief opacity fade when language changes for a smoother transition. */
  langTransitioning = signal(false);

  constructor() {
    effect(() => {
      this.notificationSocket.syncAuthToken(this.authStore.token());
    });
  }

  ngOnInit(): void {
    this.updateBreadcrumb(this.router.url);
    this.sub = this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe((e) => {
        this.updateBreadcrumb(e.urlAfterRedirects || e.url);
        this.scrollMainContentToTop();
      });
    this.langSub = this.translate.onLangChange.subscribe(() => {
      this.updateBreadcrumb(this.router.url);
      this.langTransitioning.set(true);
      setTimeout(() => this.langTransitioning.set(false), 120);
    });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.langSub?.unsubscribe();
    this.notificationSocket.syncAuthToken(null);
  }

  /** Reset scroll when switching routes; main content lives in `overflow-auto`, not `document`. */
  private scrollMainContentToTop(): void {
    requestAnimationFrame(() => {
      const el = this.mainScroll()?.nativeElement;
      if (el) el.scrollTop = 0;
      window.scrollTo(0, 0);
    });
  }

  private updateBreadcrumb(url: string): void {
    const path = url.split('?')[0];
    const segments = path.split('/').filter(Boolean);
    const labels = segments.map((seg, i) => {
      const key = seg.toLowerCase();
      if (SEGMENT_LABELS[key]) return this.i18n.t(SEGMENT_LABELS[key]);
      const isId = /^\d+$/.test(seg) || /^[0-9a-f-]{36}$/i.test(seg);
      if (isId) return this.i18n.t('BREADCRUMB.DETAIL');
      return key.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    });
    this.baseBreadcrumb.set(labels.length ? labels : [this.i18n.t('BREADCRUMB.DASHBOARD')]);
  }

  /** Toggle sidebar collapse (header return icon acts as hide/show bar). */
  toggleSidebar(): void {
    this.sidebarService.toggle();
  }

  toggleTheme(): void {
    this.theme.use(this.theme.isDark() ? 'light' : 'dark');
  }
}