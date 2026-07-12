/**
 * httpOnly session cookie helpers. Server-only.
 *
 * The backend JWT lives in an httpOnly cookie so client-side JS (and
 * any XSS payload) can never read it - a step up from the previous
 * mock implementation, which kept the whole session in localStorage
 * where any script on the page could read it.
 */
import 'server-only';
import { cookies } from 'next/headers';

const COOKIE_NAME = 'xelora_session';
const OAUTH_STATE_COOKIE = 'xelora_oauth_state';

export async function setSessionCookie(token: string, expiresAt: string) {
  const store = await cookies();
  store.set(COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    expires: new Date(expiresAt),
  });
}

export async function getSessionToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(COOKIE_NAME)?.value ?? null;
}

export async function clearSessionCookie() {
  const store = await cookies();
  store.delete(COOKIE_NAME);
}

/**
 * Short-lived CSRF protection for the OAuth login flow. A random
 * value is stored here before redirecting to Google/Microsoft, and
 * checked against what the provider echoes back in the callback -
 * without this, an attacker could trick a victim into completing an
 * OAuth flow the attacker initiated.
 */
export async function setOAuthState(state: string) {
  const store = await cookies();
  store.set(OAUTH_STATE_COOKIE, state, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: 600, // 10 minutes - the whole provider round-trip should take seconds
  });
}

/** Reads and deletes the OAuth state cookie in one step - it's only ever meant to be checked once. */
export async function consumeOAuthState(): Promise<string | null> {
  const store = await cookies();
  const value = store.get(OAUTH_STATE_COOKIE)?.value ?? null;
  store.delete(OAUTH_STATE_COOKIE);
  return value;
}
