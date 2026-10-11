import { NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function GET() {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const result = await backendFetch('/admin/subscriptions', { token });
  if (!result.ok) {
    const detail = (result.data as { detail?: string })?.detail || 'Could not load subscriptions.';
    return NextResponse.json({ error: detail }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
