import 'server-only';

import { createCipheriv, createDecipheriv, createHash, randomBytes, timingSafeEqual } from 'crypto';
import type { NextRequest, NextResponse } from 'next/server';

/**
 * Hands a browser sign-in back to Xelora Desktop.
 *
 * The desktop app opens /api/auth/<provider>/start?desktop=<secret> in the
 * user's browser. We keep only a hash of that secret in a short cookie.
 * After sign-in, the session is sealed (AES-256-GCM) into a code valid for
 * two minutes and bound to the secret's hash, and delivered to the app via
 * xelora://auth. The app redeems it together with the original secret, so a
 * leaked code alone is useless.
 */
const COOKIE = 'xelora_desktop_handoff';
const CODE_TTL_MS = 2 * 60 * 1000;
const SECRET_PATTERN = /^[A-Za-z0-9_-]{32,128}$/;

interface Handoff {
  token: string;
  expiresAt: string;
  isNewUser: boolean;
  secretHash: string;
  exp: number;
}

function key(): Buffer | null {
  const secret = process.env.XELORA_HANDOFF_SECRET || process.env.BACKEND_API_KEY || '';
  return secret ? createHash('sha256').update(`xelora-desktop-handoff:${secret}`).digest() : null;
}

export function hashSecret(secret: string): string {
  return createHash('sha256').update(secret).digest('base64url');
}

export function desktopSecretFrom(req: NextRequest): string | null {
  const secret = req.nextUrl.searchParams.get('desktop');
  return secret && SECRET_PATTERN.test(secret) && key() ? secret : null;
}

export function applyDesktopHandoffCookie(response: NextResponse, secret: string) {
  response.cookies.set(COOKIE, hashSecret(secret), {
    httpOnly: true, secure: process.env.NODE_ENV === 'production', sameSite: 'lax', path: '/', maxAge: 600,
  });
  return response;
}

export function desktopHandoffHash(req: NextRequest): string | null {
  return req.cookies.get(COOKIE)?.value ?? null;
}

export function clearDesktopHandoffCookie(response: NextResponse) {
  response.cookies.delete(COOKIE);
  return response;
}

export function sealHandoff(data: Omit<Handoff, 'exp'>): string | null {
  const k = key();
  if (!k) return null;
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', k, iv);
  const body = Buffer.concat([cipher.update(JSON.stringify({ ...data, exp: Date.now() + CODE_TTL_MS }), 'utf8'), cipher.final()]);
  return Buffer.concat([iv, cipher.getAuthTag(), body]).toString('base64url');
}

/** The sealed session, if the code is genuine, unexpired and matches the desktop's secret. */
export function openHandoff(code: string, secret: string): Handoff | null {
  const k = key();
  if (!k || !SECRET_PATTERN.test(secret)) return null;
  try {
    const raw = Buffer.from(code, 'base64url');
    const decipher = createDecipheriv('aes-256-gcm', k, raw.subarray(0, 12));
    decipher.setAuthTag(raw.subarray(12, 28));
    const data = JSON.parse(Buffer.concat([decipher.update(raw.subarray(28)), decipher.final()]).toString('utf8')) as Handoff;
    const expected = Buffer.from(hashSecret(secret));
    const actual = Buffer.from(String(data.secretHash));
    if (data.exp < Date.now() || expected.length !== actual.length || !timingSafeEqual(expected, actual)) return null;
    return data;
  } catch {
    return null;
  }
}
