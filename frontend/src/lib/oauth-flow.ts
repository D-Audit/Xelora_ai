import 'server-only';

import { randomUUID } from 'crypto';
import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import {
  applyDesktopHandoffCookie, clearDesktopHandoffCookie, desktopHandoffHash, desktopSecretFrom, sealHandoff,
} from '@/lib/desktop-handoff';
import { getOAuthOrigin, oauthFailureMessage } from '@/lib/oauth';
import { applyOAuthStateCookie, applySessionCookie, clearOAuthStateCookie, consumeOAuthState } from '@/lib/session';

export type OAuthProvider = 'google' | 'microsoft';
const LABEL: Record<OAuthProvider, string> = { google: 'Google', microsoft: 'Microsoft' };

interface ExchangeResponse {
  token: string;
  expires_at: string;
  user: Record<string, unknown>;
  is_new_user: boolean;
}

function fail(origin: string, message: string) {
  return NextResponse.redirect(`${origin}/login?error=${encodeURIComponent(message)}`);
}

/** GET /api/auth/<provider>/start: redirect to the provider's consent screen. */
export async function startOAuth(req: NextRequest, provider: OAuthProvider) {
  const origin = getOAuthOrigin(req);
  const redirectUri = `${origin}/api/auth/${provider}/callback`;
  const state = randomUUID();

  const result = await backendFetch<{ url: string }>(
    `/auth/${provider}/login?redirect_uri=${encodeURIComponent(redirectUri)}&state=${encodeURIComponent(state)}`
  );
  if (!result.ok || !('url' in result.data)) {
    return fail(origin, oauthFailureMessage(result.data, `${LABEL[provider]} sign-in is not available right now.`));
  }

  const response = applyOAuthStateCookie(NextResponse.redirect((result.data as { url: string }).url), state);
  const desktopSecret = desktopSecretFrom(req);
  return desktopSecret ? applyDesktopHandoffCookie(response, desktopSecret) : clearDesktopHandoffCookie(response);
}

/** GET /api/auth/<provider>/callback: verify state, exchange the code, start the session. */
export async function finishOAuth(req: NextRequest, provider: OAuthProvider) {
  const origin = getOAuthOrigin(req);
  const code = req.nextUrl.searchParams.get('code');
  const state = req.nextUrl.searchParams.get('state');
  const expectedState = await consumeOAuthState();

  if (req.nextUrl.searchParams.get('error')) return fail(origin, `${LABEL[provider]} sign-in was cancelled.`);
  if (!code || !state || !expectedState || state !== expectedState) {
    return fail(origin, `${LABEL[provider]} sign-in could not be verified. Please try again.`);
  }

  const result = await backendFetch<ExchangeResponse>(`/auth/${provider}/exchange`, {
    method: 'POST',
    body: { code, redirect_uri: `${origin}/api/auth/${provider}/callback` },
  });
  if (!result.ok) return fail(origin, oauthFailureMessage(result.data, `Could not complete ${LABEL[provider]} sign-in.`));

  const secretHash = desktopHandoffHash(req);
  if (secretHash) {
    // Started from Xelora Desktop: send the session back to the app.
    const sealed = sealHandoff({
      token: result.data.token, expiresAt: result.data.expires_at, isNewUser: result.data.is_new_user, secretHash,
    });
    if (sealed) {
      const response = NextResponse.redirect(`${origin}/desktop-signin?code=${encodeURIComponent(sealed)}`);
      clearOAuthStateCookie(response);
      return clearDesktopHandoffCookie(response);
    }
  }

  const response = NextResponse.redirect(`${origin}${result.data.is_new_user ? '/onboarding' : '/dashboard/agent'}`);
  clearOAuthStateCookie(response);
  return applySessionCookie(response, result.data.token, result.data.expires_at);
}
