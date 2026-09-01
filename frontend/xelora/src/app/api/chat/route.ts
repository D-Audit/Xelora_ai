import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

/**
 * Ask the backend to choose between a fast conversation response and the
 * workbook task workflow. Keeping this on the server means no API key or
 * routing policy is exposed to the browser.
 */
export async function POST(req: NextRequest) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const body = await req.json();
  const result = await backendFetch('/chat', {
    method: 'POST',
    token,
    body: {
      instruction: body.instruction,
      workbook_name: body.workbookName ?? null,
      has_workbook_context: Boolean(body.hasWorkbookContext),
      history: Array.isArray(body.history) ? body.history : [],
    },
  });

  if (!result.ok) {
    const detail =
      (result.data as { error?: string })?.error ||
      (result.data as { detail?: string })?.detail ||
      'Could not send your message.';
    return NextResponse.json({ error: detail }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
