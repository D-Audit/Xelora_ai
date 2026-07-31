import { getDesktopReleaseAssetHeaders, readDesktopReleaseAsset, DESKTOP_INSTALLER_FILE_NAME } from '@/lib/desktop-release';

export async function HEAD(): Promise<Response> {
  try {
    const headers = await getDesktopReleaseAssetHeaders(DESKTOP_INSTALLER_FILE_NAME);
    if (!headers) {
      throw new Error('No installer found');
    }

    return new Response(null, {
      headers,
    });
  } catch {
    return new Response(null, {
      status: 404,
      headers: {
        'Cache-Control': 'no-store',
      },
    });
  }
}

export async function GET(): Promise<Response> {
  try {
    const asset = await readDesktopReleaseAsset(DESKTOP_INSTALLER_FILE_NAME);
    if (!asset || typeof asset.body === 'string') {
      throw new Error('No installer found');
    }

    return new Response(asset.body, {
      headers: {
        'Content-Type': asset.contentType,
        'Content-Disposition': asset.contentDisposition ?? `attachment; filename="${DESKTOP_INSTALLER_FILE_NAME}"`,
        'Cache-Control': 'no-store',
      },
    });
  } catch {
    return new Response('Desktop installer not available yet.', {
      status: 404,
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'no-store',
      },
    });
  }
}
