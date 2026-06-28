/**
 * Power BI embed settings for the dashboard.
 * @see https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-embed-secure
 */
export const POWER_BI_OPEN_URL =
  'https://app.powerbi.com/links/A1Uj8v8ecv?ctid=dbd6664d-4eb9-46eb-99d8-5c43ba153c61&pbi_source=linkShare';

export const POWER_BI_REPORT_ID = '533a75b9-cee9-45fa-a663-4eb9f41d1750';

export const POWER_BI_TENANT_CTID = 'dbd6664d-4eb9-46eb-99d8-5c43ba153c61';

/** Global scale (1 = 100%). Applied via CSS from top-left — no side gap. */
export const POWER_BI_ZOOM_LEVEL = 0.86;

const POWER_BI_REPORT_EMBED_BASE =
  `https://app.powerbi.com/reportEmbed?reportId=${POWER_BI_REPORT_ID}` +
  `&autoAuth=true&ctid=${POWER_BI_TENANT_CTID}` +
  `&filterPaneEnabled=false&navContentPaneEnabled=false`;

function encodeEmbedConfig(config: object): string {
  const json = JSON.stringify(config);
  return btoa(
    encodeURIComponent(json).replace(/%([0-9A-F]{2})/g, (_, hex) =>
      String.fromCharCode(parseInt(hex, 16))
    )
  );
}

/** Master + FitToPage; hide filter & page nav panes (avoids left gutter). */
export function buildEmbedConfig(): object {
  return {
    layoutType: 0,
    customLayout: {
      displayOption: 0
    },
    panes: {
      filters: { expanded: false, visible: false },
      pageNavigation: { visible: false }
    }
  };
}

export function buildPowerBiEmbedUrl(): string {
  return `${POWER_BI_REPORT_EMBED_BASE}&config=${encodeEmbedConfig(buildEmbedConfig())}`;
}

export const POWER_BI_EMBED_URL = buildPowerBiEmbedUrl();

/** @deprecated alias */
export const POWER_BI_IFRAME_URL = POWER_BI_EMBED_URL;

export function canEmbedPowerBiUrl(url: string): boolean {
  if (!url?.trim()) return false;
  try {
    const u = new URL(url.trim());
    if (u.hostname !== 'app.powerbi.com') return false;
    return u.pathname.includes('/reportEmbed') || u.pathname === '/view' || u.pathname.startsWith('/view');
  } catch {
    return false;
  }
}
