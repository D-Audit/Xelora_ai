import { NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

/** Issues a local-agent token for the signed-in user (called by Xelora Desktop). */
export async function POST(req: Request) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const body = (await req.json().catch(() => ({}))) as { name?: unknown };
  const name = typeof body.name === 'string' && body.name.trim() ? body.name.trim().slice(0, 80) : 'Xelora Desktop';
  const result = await backendFetch('/agent-link/pair', { method: 'POST', body: { name }, token });
  if (!result.ok) {
    return NextResponse.json({ error: 'Could not pair this desktop.' }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
