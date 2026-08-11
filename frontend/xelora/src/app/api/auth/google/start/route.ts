import { NextRequest, NextResponse } from 'next/server';
import { randomUUID } from 'crypto';
import { backendFetch } from '@/lib/backend';
import { applyOAuthStateCookie } from '@/lib/session';
import { getOAuthOrigin, oauthFailureMessage } from '@/lib/oauth';

export async function GET(req: NextRequest) {
  const origin = getOAuthOrigin(req);
  const redirectUri = `${origin}/api/auth/google/callback`;
  const state = randomUUID();

  const result = await backendFetch<{ url: string }>(
    `/auth/google/login?redirect_uri=${encodeURIComponent(redirectUri)}&state=${encodeURIComponent(state)}`
  );

  if (!result.ok || !('url' in result.data)) {
    const message = oauthFailureMessage(result.data, 'Google sign-in is not available right now.');
    return NextResponse.redirect(`${origin}/login?error=${encodeURIComponent(message)}`);
  }

  const response = NextResponse.redirect((result.data as { url: string }).url);
  return applyOAuthStateCookie(response, state);
}
