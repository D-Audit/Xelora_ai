const GITHUB_REPO = "D-Audit/Xelora_ai";
const CACHE_TTL_MS = 5 * 60 * 1000;

interface GithubReleaseAsset {
  name: string;
  browser_download_url: string;
  size: number;
  content_type: string;
}

interface GithubRelease {
  tag_name: string;
  assets: GithubReleaseAsset[];
}

let cachedRelease: { fetchedAt: number; release: GithubRelease } | null = null;

async function getLatestRelease(): Promise<GithubRelease | null> {
  if (cachedRelease && Date.now() - cachedRelease.fetchedAt < CACHE_TTL_MS) {
    return cachedRelease.release;
  }

  const res = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/releases/latest`,
    { headers: { Accept: "application/vnd.github+json" } }
  );

  if (!res.ok) {
    return null;
  }

  const release = (await res.json()) as GithubRelease;
  cachedRelease = { fetchedAt: Date.now(), release };
  return release;
}

export async function findDesktopInstallerAsset(): Promise<GithubReleaseAsset | null> {
  const release = await getLatestRelease();
  if (!release) return null;
  return (
    release.assets.find((a) => a.name.toLowerCase().endsWith(".exe")) ?? null
  );
}

/**
 * Serve electron-updater's generic feed (latest.yml, the installer, and its
 * blockmap) from the latest GitHub release. Only an asset whose name exactly
 * matches one in that release is served; anything else is "not found".
 */
async function findReleaseAsset(assetName: string): Promise<GithubReleaseAsset | null> {
  if (!assetName || assetName.includes('/') || assetName.includes('\\') || assetName.includes('..')) {
    return null;
  }
  const release = await getLatestRelease();
  return release?.assets.find((a) => a.name === assetName) ?? null;
}

function contentTypeFor(asset: GithubReleaseAsset): string {
  const name = asset.name.toLowerCase();
  if (name.endsWith('.yml') || name.endsWith('.yaml')) return 'text/yaml; charset=utf-8';
  return asset.content_type || 'application/octet-stream';
}

export async function getDesktopReleaseAssetHeaders(assetName: string): Promise<Record<string, string> | null> {
  const asset = await findReleaseAsset(assetName);
  if (!asset) return null;
  return {
    'Content-Type': contentTypeFor(asset),
    'Content-Length': String(asset.size),
    'Cache-Control': 'no-store',
  };
}

export async function readDesktopReleaseAsset(
  assetName: string
): Promise<{ body: ReadableStream<Uint8Array>; contentType: string; contentDisposition?: string } | null> {
  const asset = await findReleaseAsset(assetName);
  if (!asset) return null;
  const res = await fetch(asset.browser_download_url, { redirect: 'follow' });
  if (!res.ok || !res.body) return null;
  const isInstaller = /\.(exe|msi|zip|blockmap)$/i.test(asset.name);
  return {
    body: res.body,
    contentType: contentTypeFor(asset),
    contentDisposition: isInstaller ? `attachment; filename="${asset.name.replace(/"/g, '')}"` : undefined,
  };
}
