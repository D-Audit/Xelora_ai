import { NextRequest, NextResponse } from 'next/server';
import { randomUUID } from 'crypto';
import { backendFetch } from '@/lib/backend';
import { setOAuthState } from '@/lib/session';

export async function GET(req: NextRequest) {
  const origin = req.nextUrl.origin;
  const redirectUri = `${origin}/api/auth/google/callback`;
  const state = randomUUID();
  await setOAuthState(state);

  const result = await backendFetch<{ url: string }>(
    `/auth/google/login?redirect_uri=${encodeURIComponent(redirectUri)}&state=${encodeURIComponent(state)}`
  );

  if (!result.ok || !('url' in result.data)) {
    const message = (result.data as { detail?: string })?.detail || 'Google sign-in is not available right now.';
    return NextResponse.redirect(`${origin}/login?error=${encodeURIComponent(message)}`);
  }

  return NextResponse.redirect((result.data as { url: string }).url);
}
