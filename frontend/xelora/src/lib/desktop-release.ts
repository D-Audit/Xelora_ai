import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';

export const DESKTOP_INSTALLER_FILE_NAME = 'Xelora-Setup.exe';
export const DESKTOP_BLOCKMAP_FILE_NAME = `${DESKTOP_INSTALLER_FILE_NAME}.blockmap`;

const desktopReleaseCandidatePaths = [
  process.env.XELORA_DESKTOP_INSTALLER_PATH,
  path.join('C:\\XeloraDesktopReleaseFresh', DESKTOP_INSTALLER_FILE_NAME),
  path.join(process.cwd(), 'apps', 'desktop', 'release', DESKTOP_INSTALLER_FILE_NAME),
  path.join(process.cwd(), 'apps', 'desktop', 'release-fresh', DESKTOP_INSTALLER_FILE_NAME),
].filter((candidate): candidate is string => Boolean(candidate));

type FileStat = Awaited<ReturnType<typeof fs.stat>>;

interface DesktopReleaseCandidate {
  installerPath: string;
  blockmapPath: string | null;
  stat: FileStat;
}

export interface DesktopReleaseBundle extends DesktopReleaseCandidate {
  version: string;
  sha512: string;
}

interface CachedBundle {
  key: string;
  bundle: DesktopReleaseBundle;
}

let cachedBundle: CachedBundle | null = null;

async function resolveCandidate(candidatePath: string): Promise<DesktopReleaseCandidate | null> {
  try {
    const candidateStat = await fs.stat(candidatePath);
    const installerPath = candidateStat.isDirectory()
      ? path.join(candidatePath, DESKTOP_INSTALLER_FILE_NAME)
      : candidatePath;
    const installerStat = candidateStat.isDirectory() ? await fs.stat(installerPath) : candidateStat;

    if (!installerStat.isFile()) {
      return null;
    }

    const blockmapPath = path.join(path.dirname(installerPath), DESKTOP_BLOCKMAP_FILE_NAME);
    const blockmapStat = await fs.stat(blockmapPath).catch(() => null);

    return {
      installerPath,
      blockmapPath: blockmapStat?.isFile() ? blockmapPath : null,
      stat: installerStat,
    };
  } catch {
    return null;
  }
}

async function readDesktopVersion(): Promise<string> {
  const packagePath = path.join(process.cwd(), 'apps', 'desktop', 'package.json');
  const raw = await fs.readFile(packagePath, 'utf8');
  const parsed = JSON.parse(raw) as { version?: string };
  return parsed.version ?? '0.1.0';
}

async function hashFile(filePath: string): Promise<string> {
  const file = await fs.readFile(filePath);
  return crypto.createHash('sha512').update(file).digest('base64');
}

export async function resolveDesktopReleaseBundle(): Promise<DesktopReleaseBundle | null> {
  let latest: DesktopReleaseCandidate | null = null;

  for (const candidatePath of desktopReleaseCandidatePaths) {
    const candidate = await resolveCandidate(candidatePath);
    if (!candidate) {
      continue;
    }

    if (!latest || candidate.stat.mtimeMs > latest.stat.mtimeMs) {
      latest = candidate;
    }
  }

  if (!latest) {
    return null;
  }

  const cacheKey = `${latest.installerPath}:${latest.stat.size}:${latest.stat.mtimeMs}`;
  if (cachedBundle?.key === cacheKey) {
    return cachedBundle.bundle;
  }

  const [version, sha512] = await Promise.all([
    readDesktopVersion(),
    hashFile(latest.installerPath),
  ]);

  const bundle: DesktopReleaseBundle = {
    ...latest,
    version,
    sha512,
  };

  cachedBundle = { key: cacheKey, bundle };
  return bundle;
}

export function renderDesktopLatestYml(bundle: DesktopReleaseBundle): string {
  const releaseDate = new Date(Number(bundle.stat.mtimeMs)).toISOString();

  return [
    `version: ${bundle.version}`,
    'files:',
    `  - url: ${path.basename(bundle.installerPath)}`,
    `    sha512: ${bundle.sha512}`,
    `    size: ${bundle.stat.size}`,
    `path: ${path.basename(bundle.installerPath)}`,
    `sha512: ${bundle.sha512}`,
    `releaseDate: ${releaseDate}`,
    '',
  ].join('\n');
}

export async function readDesktopReleaseAsset(assetName: string): Promise<{ body: string | ArrayBuffer; contentType: string; contentDisposition?: string } | null> {
  const bundle = await resolveDesktopReleaseBundle();
  if (!bundle) {
    return null;
  }

  if (assetName === 'latest.yml') {
    return {
      body: renderDesktopLatestYml(bundle),
      contentType: 'text/yaml; charset=utf-8',
    };
  }

  if (assetName === path.basename(bundle.installerPath)) {
    const file = await fs.readFile(bundle.installerPath);
    return {
      body: file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength),
      contentType: 'application/octet-stream',
      contentDisposition: `attachment; filename="${path.basename(bundle.installerPath)}"`,
    };
  }

  if (assetName === DESKTOP_BLOCKMAP_FILE_NAME && bundle.blockmapPath) {
    const file = await fs.readFile(bundle.blockmapPath);
    return {
      body: file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength),
      contentType: 'application/octet-stream',
      contentDisposition: `attachment; filename="${path.basename(bundle.blockmapPath)}"`,
    };
  }

  return null;
}

export async function getDesktopReleaseAssetHeaders(assetName: string): Promise<HeadersInit | null> {
  const bundle = await resolveDesktopReleaseBundle();
  if (!bundle) {
    return null;
  }

  if (assetName === 'latest.yml') {
    return {
      'Content-Type': 'text/yaml; charset=utf-8',
      'Cache-Control': 'no-store',
    };
  }

  if (assetName === path.basename(bundle.installerPath)) {
    return {
      'Content-Type': 'application/octet-stream',
      'Content-Disposition': `attachment; filename="${path.basename(bundle.installerPath)}"`,
      'Content-Length': String(bundle.stat.size),
      'Cache-Control': 'no-store',
    };
  }

  if (assetName === DESKTOP_BLOCKMAP_FILE_NAME && bundle.blockmapPath) {
    const blockmapStat = await fs.stat(bundle.blockmapPath);
    return {
      'Content-Type': 'application/octet-stream',
      'Content-Disposition': `attachment; filename="${path.basename(bundle.blockmapPath)}"`,
      'Content-Length': String(blockmapStat.size),
      'Cache-Control': 'no-store',
    };
  }

  return null;
}
