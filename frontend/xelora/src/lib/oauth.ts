import 'server-only';

import type { NextRequest } from 'next/server';

/**
 * OAuth providers require one exact callback URL.  In development the app
 * may be opened through localhost or 127.0.0.1, which are different URLs to
 * Google.  Prefer a configured public app URL so the start and callback
 * endpoints always use the registered value.
 */
export function getOAuthOrigin(request: NextRequest): string {
  const configuredOrigin = process.env.XELORA_APP_URL?.trim().replace(/\/+$/, '');
  return configuredOrigin || request.nextUrl.origin;
}

export function oauthFailureMessage(data: unknown, fallback: string): string {
  if (data && typeof data === 'object') {
    const value = data as { error?: unknown; detail?: unknown };
    if (typeof value.error === 'string' && value.error) return value.error;
    if (typeof value.detail === 'string' && value.detail) return value.detail;
  }
  return fallback;
}
