import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { setSessionCookie } from '@/lib/session';

interface LoginBackendResponse {
  token: string;
  expires_at: string;
  user: Record<string, unknown>;
}

export async function POST(req: NextRequest) {
  const body = await req.json();

  const result = await backendFetch<LoginBackendResponse>('/auth/login', {
    method: 'POST',
    body: { email: body.email, password: body.password },
  });

  if (!result.ok) {
    const detail =
      (result.data as { detail?: string })?.detail ||
      (result.data as { error?: string })?.error ||
      'Invalid email address or password.';
    return NextResponse.json({ error: detail }, { status: result.status || 401 });
  }

  await setSessionCookie(result.data.token, result.data.expires_at);
  return NextResponse.json({ user: result.data.user });
}
