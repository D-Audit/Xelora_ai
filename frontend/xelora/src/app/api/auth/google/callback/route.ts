import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { applySessionCookie, clearOAuthStateCookie, consumeOAuthState } from '@/lib/session';

interface ExchangeResponse {
  token: string;
  expires_at: string;
  user: Record<string, unknown>;
  is_new_user: boolean;
}

export async function GET(req: NextRequest) {
  const origin = req.nextUrl.origin;
  const code = req.nextUrl.searchParams.get('code');
  const state = req.nextUrl.searchParams.get('state');
  const errorParam = req.nextUrl.searchParams.get('error');

  const expectedState = await consumeOAuthState();

  if (errorParam) {
    return NextResponse.redirect(`${origin}/login?error=${encodeURIComponent('Google sign-in was cancelled.')}`);
  }
  if (!code || !state || !expectedState || state !== expectedState) {
    return NextResponse.redirect(
      `${origin}/login?error=${encodeURIComponent('Google sign-in could not be verified. Please try again.')}`
    );
  }

  const redirectUri = `${origin}/api/auth/google/callback`;
  const result = await backendFetch<ExchangeResponse>('/auth/google/exchange', {
    method: 'POST',
    body: { code, redirect_uri: redirectUri },
  });

  if (!result.ok) {
    const message = (result.data as { detail?: string })?.detail || 'Could not complete Google sign-in.';
    return NextResponse.redirect(`${origin}/login?error=${encodeURIComponent(message)}`);
  }

  const destination = result.data.is_new_user ? '/onboarding' : '/dashboard';
  const response = NextResponse.redirect(`${origin}${destination}`);
  clearOAuthStateCookie(response);
  return applySessionCookie(response, result.data.token, result.data.expires_at);
}
