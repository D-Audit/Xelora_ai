import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function POST(req: NextRequest) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const body = await req.json();
  const result = await backendFetch('/team/invite', {
    method: 'POST',
    token,
    body: { email: body.email, role: body.role },
  });
  if (!result.ok) {
    const detail = (result.data as { detail?: string })?.detail || 'Could not send invite.';
    return NextResponse.json({ error: detail }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
