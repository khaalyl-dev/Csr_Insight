import {
  faTachometerAlt,
  faList,
  faCheckSquare,
  faClipboardCheck,
  faEnvelopeOpenText,
  faHourglassHalf,
  faHistory,
  faUser,
  faBuilding,
  faFolderTree,
  faFolderOpen,
  faCalendarPlus,
  faClipboardList,
  faChartLine,
} from '@fortawesome/free-solid-svg-icons';

export interface NavItem {
  labelKey: string;
  path: string;
  roles: ('site' | 'corporate')[];
  icon: any;
  permissionAny?: string[];
  requiresValidatorLevel?: boolean;
  requiresCreatorLevel?: boolean;
}

export interface NavSection {
  sectionKey: string;
  roles: ('site' | 'corporate')[];
  isDropdown?: boolean;
  /** When true, do not show section header (e.g. Dashboard first). */
  hideSectionLabel?: boolean;
  items: NavItem[];
}

export const navItems: NavSection[] = [
  {
    sectionKey: '',
    roles: ['site', 'corporate'],
    hideSectionLabel: true,
    items: [
      { labelKey: 'NAV.ITEMS.DASHBOARD', path: '/dashboard', roles: ['site', 'corporate'], icon: faChartLine, permissionAny: ['dashboard.read'] },
    ],
  },
  {
    sectionKey: 'NAV.SECTIONS.PLANS_ACTIVITIES',
    roles: ['site', 'corporate'],
    isDropdown: true,
    items: [
      { labelKey: 'NAV.ITEMS.ANNUAL_PLANS', path: '/csr-plans', roles: ['site', 'corporate'], icon: faList, permissionAny: ['plan.read'] },
      { labelKey: 'NAV.ITEMS.REALIZED_ACTIVITIES', path: '/realized-csr', roles: ['site', 'corporate'], icon: faClipboardCheck, permissionAny: ['realized_activity.read'] },
      { labelKey: 'NAV.ITEMS.PLANNED_ACTIVITIES', path: '/planned-activities', roles: ['site', 'corporate'], icon: faCalendarPlus, permissionAny: ['activity.read'] },
      { labelKey: 'NAV.ITEMS.DOCUMENTS', path: '/documents', roles: ['site', 'corporate'], icon: faFolderOpen, permissionAny: ['document.read'] },
    ],
  },
  {
    sectionKey: 'NAV.SECTIONS.APPROVALS',
    roles: ['site', 'corporate'],
    isDropdown: true,
    items: [
      { labelKey: 'NAV.ITEMS.VALIDATE_PLANS', path: '/annual-plans/validation', roles: ['site', 'corporate'], icon: faCheckSquare, permissionAny: ['plan.validate', 'activity.validate'], requiresValidatorLevel: true },
      { labelKey: 'NAV.ITEMS.MY_REQUESTS', path: '/changes', roles: ['site'], icon: faEnvelopeOpenText, permissionAny: ['change_request.read'], requiresCreatorLevel: true },
      { labelKey: 'NAV.ITEMS.PENDING_REQUESTS', path: '/changes/pending', roles: ['site', 'corporate'], icon: faHourglassHalf, permissionAny: ['change_request.review'], requiresValidatorLevel: true },
      { labelKey: 'NAV.ITEMS.CHANGE_HISTORY', path: '/changes/history', roles: ['corporate'], icon: faHistory, permissionAny: ['change_request.history'] },
    ],
  },
  {
    sectionKey: 'NAV.SECTIONS.SETTINGS',
    roles: ['corporate'],
    isDropdown: true,
    items: [
      { labelKey: 'NAV.ITEMS.SITES', path: '/sites', roles: ['corporate'], icon: faBuilding, permissionAny: ['site.read'] },
      { labelKey: 'NAV.ITEMS.CSR_CATEGORIES', path: '/categories', roles: ['corporate'], icon: faFolderTree, permissionAny: ['category.read'] },
      { labelKey: 'NAV.ITEMS.USERS', path: '/admin/users', roles: ['corporate'], icon: faUser, permissionAny: ['user.read'] },
      { labelKey: 'NAV.ITEMS.AUDIT_LOG', path: '/admin/audit', roles: ['corporate'], icon: faClipboardList, permissionAny: ['audit_log.read'] },
    ],
  },
];
