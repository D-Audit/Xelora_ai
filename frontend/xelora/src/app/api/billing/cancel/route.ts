import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function POST(req: NextRequest) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const body = await req.json().catch(() => ({}));
  const result = await backendFetch('/billing/cancel', {
    method: 'POST',
    token,
    body: { immediately: body.immediately ?? false },
  });

  if (!result.ok) {
    const detail = (result.data as { detail?: string })?.detail || 'Could not cancel subscription.';
    return NextResponse.json({ error: detail }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
