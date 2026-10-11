import { getDesktopReleaseAssetHeaders, readDesktopReleaseAsset } from '@/lib/desktop-release';
import type { NextRequest } from 'next/server';

interface RouteContext {
  params: Promise<{
    asset?: string[];
  }>;
}

async function getAssetName(context: RouteContext): Promise<string> {
  const { asset } = await context.params;
  return asset?.join('/') ?? '';
}

export async function HEAD(_request: NextRequest, context: RouteContext): Promise<Response> {
  try {
    const assetName = await getAssetName(context);
    const headers = await getDesktopReleaseAssetHeaders(assetName);

    if (!headers) {
      throw new Error('Desktop release asset not found');
    }

    return new Response(null, { headers });
  } catch {
    return new Response(null, {
      status: 404,
      headers: {
        'Cache-Control': 'no-store',
      },
    });
  }
}

export async function GET(_request: NextRequest, context: RouteContext): Promise<Response> {
  try {
    const assetName = await getAssetName(context);
    const asset = await readDesktopReleaseAsset(assetName);

    if (!asset) {
      throw new Error('Desktop release asset not found');
    }

    return new Response(asset.body, {
      headers: {
        'Content-Type': asset.contentType,
        ...(asset.contentDisposition ? { 'Content-Disposition': asset.contentDisposition } : {}),
        'Cache-Control': 'no-store',
      },
    });
  } catch {
    return new Response('Desktop release asset not available yet.', {
      status: 404,
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'no-store',
      },
    });
  }
}
