import { getSessionToken } from '@/lib/session';
import { backendHeaders, backendUrl } from '@/lib/backend';

export const dynamic = 'force-dynamic';

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const token = await getSessionToken();
  if (!token) return Response.json({ error: 'Not signed in.' }, { status: 401 });

  const { id } = await params;
  let upstream: Response;
  try {
    upstream = await fetch(backendUrl(`/task/${id}/events`), {
      headers: backendHeaders(token),
      cache: 'no-store',
      signal: req.signal,
    });
  } catch {
    return Response.json({ error: 'Could not reach the Xelora backend.' }, { status: 502 });
  }

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.json().catch(() => ({}));
    return Response.json(detail, { status: upstream.status });
  }

  // Forward the ReadableStream itself. Calling json()/text() here would buffer
  // the provider output and destroy time-to-first-token.
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      'Content-Type': 'application/x-ndjson; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      'X-Accel-Buffering': 'no',
    },
  });
}
