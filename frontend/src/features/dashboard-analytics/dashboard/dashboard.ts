import {
  Component,
  inject,
  OnDestroy,
  OnInit,
  signal
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { TranslateModule } from '@ngx-translate/core';
import {
  POWER_BI_ZOOM_LEVEL,
  buildPowerBiEmbedUrl,
  POWER_BI_OPEN_URL,
  canEmbedPowerBiUrl
} from './power-bi.config';

/** Hide spinner if Power BI SDK events never fire (e.g. sign-in screen inside iframe). */
const LOADING_TIMEOUT_MS = 12_000;

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, TranslateModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class Dashboard implements OnInit, OnDestroy {
  private readonly sanitizer = inject(DomSanitizer);

  readonly powerBiOpenUrl = POWER_BI_OPEN_URL;
  /** Applied on the iframe — works with autoAuth (unlike URL settings.zoomLevel). */
  readonly powerBiZoom = POWER_BI_ZOOM_LEVEL;

  private readonly embedUrl = buildPowerBiEmbedUrl();
  readonly canEmbed = canEmbedPowerBiUrl(this.embedUrl);
  readonly powerBiSafeUrl: SafeResourceUrl | null = this.canEmbed
    ? this.sanitizer.bypassSecurityTrustResourceUrl(this.embedUrl)
    : null;

  iframeLoading = signal(!!this.canEmbed);
  loadHint = signal(false);

  private loadingTimeoutId: ReturnType<typeof setTimeout> | null = null;

  ngOnInit(): void {
    document.body.classList.add('dashboard-powerbi-active');
    document.documentElement.style.overflow = 'hidden';

    if (this.canEmbed) {
      this.loadingTimeoutId = setTimeout(() => {
        this.iframeLoading.set(false);
        this.loadHint.set(true);
      }, LOADING_TIMEOUT_MS);
    }
  }

  ngOnDestroy(): void {
    document.body.classList.remove('dashboard-powerbi-active');
    document.documentElement.style.overflow = '';
    if (this.loadingTimeoutId) {
      clearTimeout(this.loadingTimeoutId);
    }
  }

  onIframeLoad(): void {
    this.iframeLoading.set(false);
    this.loadHint.set(false);
    if (this.loadingTimeoutId) {
      clearTimeout(this.loadingTimeoutId);
      this.loadingTimeoutId = null;
    }
  }

  openPowerBi(): void {
    window.open(this.powerBiOpenUrl, '_blank', 'noopener,noreferrer');
  }
}
