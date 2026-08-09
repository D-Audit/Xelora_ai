/**
 * Server-only helper for calling the FastAPI backend.
 *
 * IMPORTANT: this file must only ever be imported from Next.js Route
 * Handlers (src/app/api/**\/route.ts) or Server Components - never
 * from a 'use client' file. It reads BACKEND_URL and BACKEND_API_KEY
 * from process.env, which are only available server-side. This is
 * what keeps the backend's shared LOCAL_API_KEY out of the browser:
 * the browser talks to our Next.js API routes, and only this file
 * (running on the Next.js server) talks to FastAPI directly.
 */
import 'server-only';

const BACKEND_URL = (process.env.BACKEND_URL || 'http://localhost:8000').replace(/\/+$/, '');
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || '';

export interface BackendResult<T = unknown> {
  ok: boolean;
  status: number;
  data: T;
}

/** Build authenticated server-to-server headers for non-JSON requests. */
export function backendHeaders(token?: string | null): Record<string, string> {
  const headers: Record<string, string> = {};
  if (BACKEND_API_KEY) headers['X-API-Key'] = BACKEND_API_KEY;
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

/** Resolve a backend path without exposing the backend URL to the browser. */
export function backendUrl(path: string): string {
  return `${BACKEND_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

/**
 * Calls the FastAPI backend. Always attaches X-API-Key (the shared
 * server-to-server secret). Pass `token` to also forward a user's JWT
 * as a Bearer token for endpoints that require per-user identity
 * (/auth/me, /billing/*, /task).
 */
export async function backendFetch<T = unknown>(
  path: string,
  options: {
    method?: 'GET' | 'POST' | 'DELETE' | 'PATCH';
    body?: unknown;
    token?: string | null;
  } = {}
): Promise<BackendResult<T>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...backendHeaders(options.token),
  };

  let res: Response;
  try {
    res = await fetch(backendUrl(path), {
      method: options.method || 'GET',
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      cache: 'no-store',
    });
  } catch {
    return {
      ok: false,
      status: 502,
      data: { error: 'Could not reach the backend. Is it running at ' + BACKEND_URL + '?' } as T,
    };
  }

  let data: T;
  try {
    data = (await res.json()) as T;
  } catch {
    data = {} as T;
  }

  return { ok: res.ok, status: res.status, data };
}
