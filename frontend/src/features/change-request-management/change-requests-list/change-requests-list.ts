import { Component, OnInit, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { ChangeRequestsApi, type ChangeRequestWithDocs } from '../api/change-requests-api';
import { UserAvatarNameComponent } from '@shared/components/user-avatar-name/user-avatar-name';

@Component({
  selector: 'app-change-requests-list',
  standalone: true,
  imports: [CommonModule, RouterModule, TranslateModule, UserAvatarNameComponent],
  templateUrl: './change-requests-list.html',
})
export class ChangeRequestsListComponent implements OnInit {
  private api = inject(ChangeRequestsApi);
  private translate = inject(TranslateService);
  requests = signal<ChangeRequestWithDocs[]>([]);
  loading = signal(true);

  ngOnInit(): void {
    this.api.list().subscribe({
      next: (list) => {
        this.requests.set(list);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  statusLabel(s: string): string {
    const keyMap: Record<string, string> = {
      PENDING: 'CHANGE_REQUEST.STATUS_PENDING',
      SUBMITTED: 'CHANGE_REQUEST.STATUS_PENDING',
      APPROVED: 'CHANGE_REQUEST.STATUS_APPROVED',
      VALIDATED: 'CHANGE_REQUEST.STATUS_APPROVED',
      REJECTED: 'CHANGE_REQUEST.STATUS_REJECTED',
    };
    const key = keyMap[s];
    return key ? this.translate.instant(key) : s;
  }

  isOffPlanRow(r: ChangeRequestWithDocs): boolean {
    return r.pending_item_type === 'OFF_PLAN_ACTIVITY';
  }

  isInPlanModRow(r: ChangeRequestWithDocs): boolean {
    return r.pending_item_type === 'IN_PLAN_ACTIVITY_MOD';
  }

  isSyntheticActivityRow(r: ChangeRequestWithDocs): boolean {
    return this.isOffPlanRow(r) || this.isInPlanModRow(r);
  }

  isPlanValidationRow(r: ChangeRequestWithDocs): boolean {
    return r.pending_item_type === 'PLAN_VALIDATION';
  }

  /** Plan detail route id (plan UUID), not activity id. */
  planDetailId(r: ChangeRequestWithDocs): string {
    if (r.plan_id) return r.plan_id;
    if (r.entity_type === 'PLAN') return r.entity_id;
    return r.entity_id;
  }
}
