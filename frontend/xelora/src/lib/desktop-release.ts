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
