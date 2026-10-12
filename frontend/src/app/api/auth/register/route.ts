import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { backendErrorMessage } from '@/lib/relay';
import { setSessionCookie } from '@/lib/session';

interface RegisterBackendResponse {
  token: string;
  expires_at: string;
  user: Record<string, unknown>;
}

export async function POST(req: NextRequest) {
  const body = await req.json();

  const result = await backendFetch<RegisterBackendResponse>('/auth/register', {
    method: 'POST',
    body: {
      name: body.name,
      email: body.email,
      password: body.password,
      country: body.country ?? null,
      primary_use: body.primaryUse ?? null,
    },
  });

  if (!result.ok) {
    const detail = backendErrorMessage(result.data, 'Registration failed.');
    return NextResponse.json({ error: detail }, { status: result.status || 500 });
  }

  await setSessionCookie(result.data.token, result.data.expires_at);
  return NextResponse.json({ user: result.data.user });
}
