/**
 * Authentication service - talks to our own Next.js API routes
 * (/api/auth/*), which forward to the FastAPI backend server-side.
 * The session token itself lives in an httpOnly cookie set by those
 * routes; this file never touches it directly, and no token is ever
 * stored in localStorage.
 *
 * Function names/signatures are kept the same as the previous mock
 * implementation so the login/register pages, onboarding page, and
 * auth-store.ts didn't need to change.
 */
import type { User } from '@/types';

export interface AuthSession {
  user: User;
}

function mapBackendUser(raw: Record<string, unknown>): User {
  return {
    id: raw.id as string,
    name: raw.name as string,
    email: raw.email as string,
    role: 'owner',
    plan: (raw.plan as User['plan']) ?? 'trial',
    createdAt: (raw.createdAt as string) ?? new Date().toISOString(),
    lastActiveAt: new Date().toISOString(),
    isVerified: Boolean(raw.isVerified),
    onboardingCompleted: Boolean(raw.onboardingCompleted),
    isAdmin: Boolean(raw.isAdmin),
  };
}

export async function login(email: string, password: string): Promise<AuthSession> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || 'Invalid email address or password. Please try again.');
  }
  return { user: mapBackendUser(data.user) };
}

export async function register(data: {
  name: string;
  email: string;
  password: string;
  country: string;
  primaryUse: string;
}): Promise<AuthSession> {
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const body = await res.json();
  if (!res.ok) {
    throw new Error(body.error || 'An account with this email already exists.');
  }
  return { user: mapBackendUser(body.user) };
}

export async function getSession(): Promise<AuthSession | null> {
  const res = await fetch('/api/auth/me', { cache: 'no-store' });
  if (!res.ok) return null;
  const data = await res.json();
  if (!data.user) return null;
  return { user: mapBackendUser(data.user) };
}

export async function logout(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST' });
}

/**
 * Onboarding answers (primaryUse, experience, objectives, etc.) are not
 * currently modeled on the backend - the added AuthUser table only
 * covers auth + plan. This updates the in-memory session view so the
 * UI reflects the change immediately; it is NOT persisted server-side
 * yet. See INTEGRATION.md if you want to add those columns.
 */
export function updateSession(_updates: Partial<User>): void {
  // Intentionally a no-op against the backend - see docstring above.
  // auth-store.ts's setUser() is what actually updates the UI state;
  // callers should use that for the visible effect.
}
