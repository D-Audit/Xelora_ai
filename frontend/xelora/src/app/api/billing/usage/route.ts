import { NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function GET() {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });
  const result = await backendFetch('/billing/usage', { token });
  if (!result.ok) return NextResponse.json({ error: 'Could not load usage.' }, { status: result.status || 500 });
  return NextResponse.json(result.data);
}
