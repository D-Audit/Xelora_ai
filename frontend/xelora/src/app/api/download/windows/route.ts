import { findDesktopInstallerAsset } from "@/lib/desktop-release";

export async function GET(): Promise<Response> {
  const asset = await findDesktopInstallerAsset();

  if (!asset) {
    return new Response("Desktop installer not available yet.", {
      status: 404,
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Cache-Control": "no-store",
      },
    });
  }

  return Response.redirect(asset.browser_download_url, 302);
}

export async function HEAD(): Promise<Response> {
  const asset = await findDesktopInstallerAsset();

  if (!asset) {
    return new Response(null, { status: 404, headers: { "Cache-Control": "no-store" } });
  }

  return new Response(null, {
    headers: {
      "Content-Type": asset.content_type,
      "Content-Length": String(asset.size),
      "Cache-Control": "no-store",
    },
  });
}
