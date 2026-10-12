import 'server-only';

import { randomUUID } from 'crypto';
import { NextRequest, NextResponse, after } from 'next/server';
import { backendFetch, wakeBackend } from '@/lib/backend';
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

/**
 * Google's consent URL needs only the public client ID, so when Vercel has
 * GOOGLE_CLIENT_ID it is built here and Google opens without waiting on the
 * backend. Must match backend/oauth.py google_login().
 */
function googleAuthorizeUrl(redirectUri: string, state: string): string | null {
  const clientId = process.env.GOOGLE_CLIENT_ID?.trim();
  if (!clientId) return null;
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'openid email profile',
    access_type: 'online',
    prompt: 'select_account',
    state,
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
}

/** GET /api/auth/<provider>/start: redirect to the provider's consent screen. */
export async function startOAuth(req: NextRequest, provider: OAuthProvider) {
  const origin = getOAuthOrigin(req);
  const redirectUri = `${origin}/api/auth/${provider}/callback`;
  const state = randomUUID();
  // The callback needs the backend; let it boot while the user signs in.
  after(wakeBackend);

  let url = provider === 'google' ? googleAuthorizeUrl(redirectUri, state) : null;
  if (!url) {
    const result = await backendFetch<{ url: string }>(
      `/auth/${provider}/login?redirect_uri=${encodeURIComponent(redirectUri)}&state=${encodeURIComponent(state)}`
    );
    if (!result.ok || !('url' in result.data)) {
      return fail(origin, oauthFailureMessage(result.data, `${LABEL[provider]} sign-in is not available right now.`));
    }
    url = (result.data as { url: string }).url;
  }

  const response = applyOAuthStateCookie(NextResponse.redirect(url), state);
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

  // Signed in on the website: hand off to Xelora Desktop (the workspace is desktop-only).
  const response = NextResponse.redirect(`${origin}/open${result.data.is_new_user ? '?welcome=1' : ''}`);
  clearOAuthStateCookie(response);
  return applySessionCookie(response, result.data.token, result.data.expires_at);
}
