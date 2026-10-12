import { NextRequest, NextResponse } from 'next/server';
import { relayJson } from '@/lib/relay';
import { backendFetch } from '@/lib/backend';
import { getSessionToken, clearSessionCookie } from '@/lib/session';

export async function GET() {
  const token = await getSessionToken();
  if (!token) {
    return NextResponse.json({ user: null }, { status: 200 });
  }

  const result = await backendFetch<Record<string, unknown>>('/auth/me', { token });

  if (!result.ok) {
    await clearSessionCookie();
    return NextResponse.json({ user: null }, { status: 200 });
  }

  return NextResponse.json({ user: result.data });
}

export async function PATCH(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  return relayJson('/auth/me', { method: 'PATCH', auth: true, body: { name: body.name } });
}
