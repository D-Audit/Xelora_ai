import { NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function POST() {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const result = await backendFetch('/notifications/read-all', { method: 'POST', token });
  if (!result.ok) {
    return NextResponse.json({ error: 'Could not update notifications.' }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
