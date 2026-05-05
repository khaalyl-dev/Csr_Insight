/**
 * App routing configuration.
 * /account/profile - Profile page (Mon Profil), accessible to all authenticated users.
 */
import { Routes } from '@angular/router';
import { Login } from '@features/user-management/login/login';
import { Dashboard } from '@features/dashboard-analytics/dashboard/dashboard';
import { MainLayout } from '@shared/layouts/main-layout/main-layout';
import { authGuard, roleGuard, permissionGuard, validatorLevelGuard } from '@core/guards/auth.guard';
import { AnnualPlansComponent } from '@features/csr-plan-management/annual-plans/annual-plans';
import { SitesListComponent } from '@features/site-management/sites-list/sites-list';
import { UsersListComponent } from '@features/user-management/users-list/users-list';
import { UserDetailComponent } from '@features/user-management/user-detail/user-detail';
import { ProfileSettingsComponent } from '@features/user-management/profile-settings/profile-settings';
import { SiteFormComponent } from '@features/site-management/site-form/site-form';
import { EditSiteComponent } from '@features/site-management/edit-site/edit-site';
import { SiteUsersComponent } from '@features/site-management/site-users/site-users';
import { RealizedListComponent } from '@features/realized-activity-management/realized-list/realized-list';
import { RealizedDetailComponent } from '@features/realized-activity-management/realized-detail/realized-detail';
import { PlanDetailComponent } from '@features/csr-plan-management/plan-detail/plan-detail';
import { PlanEditComponent } from '@features/csr-plan-management/plan-edit/plan-edit';
import { PlanValidationComponent } from '@features/csr-plan-management/plan-validation/plan-validation';
import { PlannedActivityDetailComponent } from '@features/planned-activity-management/planned-activity-detail/planned-activity-detail';
import { PlannedActivityEditComponent } from '@features/planned-activity-management/planned-activity-edit/planned-activity-edit';
import { PlannedActivitiesListComponent } from '@features/planned-activity-management/planned-activities-list/planned-activities-list';
import { RealizedEditComponent } from '@features/realized-activity-management/realized-edit/realized-edit';
import { DocumentsListComponent } from '@features/file-management/documents-list/documents-list';
import { CategoriesListComponent } from '@features/site-management/categories-list/categories-list';
import { ChangeRequestCreateComponent } from '@features/change-request-management/change-request-create/change-request-create';
import { ChangeRequestsListComponent } from '@features/change-request-management/change-requests-list/change-requests-list';
import { ChangeRequestsPendingComponent } from '@features/change-request-management/change-requests-pending/change-requests-pending';
import { ChangeRequestsHistoryComponent } from '@features/change-request-management/change-requests-history/change-requests-history';
import { ChangeRequestDetailComponent } from '@features/change-request-management/change-request-detail/change-request-detail';
import { AuditListComponent } from '@features/audit-history-management/audit-list/audit-list';

export const routes: Routes = [
  { path: 'login', component: Login },
  {
    path: '',
    component: MainLayout,
    canActivate: [authGuard],
    children: [
      { path: 'dashboard', component: Dashboard },
      { path: 'dashboard/corporate', component: Dashboard, canActivate: [roleGuard(['corporate'])] },
      { path: 'dashboard/site', component: Dashboard, canActivate: [roleGuard(['site'])] },
      { path: 'csr-plans', component: AnnualPlansComponent, canActivate: [permissionGuard(['plan.read'])] },
      { path: 'csr-plans/:id', component: PlanDetailComponent, canActivate: [permissionGuard(['plan.read'])] },
      { path: 'csr-plans/:id/edit', component: PlanEditComponent },
      { path: 'annual-plans/validation', component: PlanValidationComponent, canActivate: [validatorLevelGuard, permissionGuard(['plan.validate', 'activity.validate'])] },
      { path: 'planned-activities', component: PlannedActivitiesListComponent, canActivate: [permissionGuard(['activity.read'])] },
      { path: 'planned-activity/:id/edit', component: PlannedActivityEditComponent },
      { path: 'planned-activity/:id', component: PlannedActivityDetailComponent, canActivate: [permissionGuard(['activity.read'])] },
      { path: 'realized-csr', component: RealizedListComponent, canActivate: [permissionGuard(['realized_activity.read'])] },
      { path: 'realized-csr/:id/edit', component: RealizedEditComponent },
      { path: 'realized-csr/:id', component: RealizedDetailComponent },
      { path: 'sites', component: SitesListComponent, canActivate: [roleGuard(['corporate']), permissionGuard(['site.read'])] },
      { path: 'categories', component: CategoriesListComponent, canActivate: [roleGuard(['corporate']), permissionGuard(['category.read'])] },
      { path: 'sites/create', component: SiteFormComponent, canActivate: [roleGuard(['corporate'])] },
      { path: 'sites/edit/:id', component: EditSiteComponent, canActivate: [roleGuard(['corporate'])] },
      { path: 'admin/users', component: UsersListComponent, canActivate: [roleGuard(['corporate']), permissionGuard(['user.read'])] },
      { path: 'admin/users/:id', component: UserDetailComponent, canActivate: [roleGuard(['corporate']), permissionGuard(['user.read'])] },
      { path: 'account/profile', component: ProfileSettingsComponent },
      {path: 'sites/:id/users', component: SiteUsersComponent},
      { path: 'documents', component: DocumentsListComponent, canActivate: [permissionGuard(['document.read'])] },
      { path: 'changes', component: ChangeRequestsListComponent, canActivate: [permissionGuard(['change_request.read'])] },
      { path: 'changes/create', component: ChangeRequestCreateComponent, canActivate: [permissionGuard(['change_request.create'])] },
      { path: 'changes/pending', component: ChangeRequestsPendingComponent, canActivate: [roleGuard(['site', 'corporate']), validatorLevelGuard, permissionGuard(['change_request.review'])] },
      { path: 'changes/history', component: ChangeRequestsHistoryComponent, canActivate: [roleGuard(['corporate']), permissionGuard(['change_request.history'])] },
      { path: 'changes/:id', component: ChangeRequestDetailComponent },
      { path: 'admin/audit', component: AuditListComponent, canActivate: [roleGuard(['corporate']), permissionGuard(['audit_log.read'])] },

      { path: '', redirectTo: 'dashboard', pathMatch: 'full' }
    ]
  },
  { path: '**', redirectTo: 'dashboard' }
];
