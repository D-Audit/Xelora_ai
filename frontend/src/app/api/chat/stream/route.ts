import { NextRequest, NextResponse } from 'next/server';
import { backendHeaders, backendUrl } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

// A quick answer may search the web and fall back across models (the backend
// caps it at about 45 seconds), and a sleeping backend adds its cold start.
export const maxDuration = 120;

/**
 * Streams /chat/stream from the backend: newline-delimited JSON events
 * (route, status, ping, answer), so the composer can show what Xelora is
 * doing while it answers instead of a silent spinner.
 */
export async function POST(req: NextRequest) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const body = await req.json();
  let upstream: Response;
  try {
    upstream = await fetch(backendUrl('/chat/stream'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...backendHeaders(token) },
      body: JSON.stringify({
        instruction: body.instruction,
        workbook_name: body.workbookName ?? null,
        has_workbook_context: Boolean(body.hasWorkbookContext),
        history: Array.isArray(body.history) ? body.history : [],
        task_id: typeof body.taskId === 'number' ? body.taskId : null,
      }),
      cache: 'no-store',
      signal: req.signal,
    });
  } catch {
    return NextResponse.json({ error: 'Could not reach Xelora. Check your connection and try again.' }, { status: 502 });
  }

  if (!upstream.ok || !upstream.body) {
    const data = await upstream.json().catch(() => ({}));
    const detail = (data as { error?: string; detail?: string }).error
      || (data as { detail?: string }).detail
      || 'Could not send your message.';
    return NextResponse.json({ error: detail }, { status: upstream.status || 500 });
  }

  return new Response(upstream.body, {
    headers: {
      'Content-Type': 'application/x-ndjson; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      'X-Accel-Buffering': 'no',
    },
  });
}
