import 'server-only';

import { NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

/** Turns a FastAPI error body (string detail or validation list) into one readable message. */
export function backendErrorMessage(data: unknown, fallback: string): string {
  const value = data as { detail?: unknown; error?: unknown } | null;
  if (typeof value?.detail === 'string') return value.detail;
  if (typeof value?.error === 'string') return value.error;
  if (Array.isArray(value?.detail) && value.detail.length) {
    const first = value.detail[0] as { loc?: unknown[]; msg?: string };
    const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : '';
    if (field === 'password' || field === 'new_password') return 'Password must be at least 8 characters.';
    if (field === 'email') return 'Please enter a valid email address.';
    if (first.msg) return first.msg;
  }
  return fallback;
}

/** Forward a JSON request to the backend, optionally as the signed-in user. */
export async function relayJson(
  path: string,
  { method = 'POST', body, auth = false, fallback = 'Something went wrong. Please try again.' }:
  { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; body?: unknown; auth?: boolean; fallback?: string } = {},
) {
  const token = auth ? await getSessionToken() : null;
  if (auth && !token) return NextResponse.json({ error: 'Please sign in again.' }, { status: 401 });
  const result = await backendFetch(path, { method, body, token });
  if (!result.ok) {
    return NextResponse.json({ error: backendErrorMessage(result.data, fallback) }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
