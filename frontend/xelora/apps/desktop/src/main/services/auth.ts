import { randomUUID } from 'node:crypto';
import fs from 'node:fs/promises';
import type { LoginRequest, LoginResult, SessionState, UserProfile } from '../../shared/types';
import { createUserDataPath } from './store';

export const DEMO_EMAIL = 'liliane@xelora.app';
export const DEMO_PASSWORD = 'Demo123!';

function createDemoUser(): UserProfile {
  return {
    id: 'demo-user',
    name: 'Liliane',
    email: DEMO_EMAIL,
    role: 'Operations Analyst',
  };
}

export function createSession(request: LoginRequest): SessionState {
  if (request.email.toLowerCase() !== DEMO_EMAIL || request.password !== DEMO_PASSWORD) {
    throw new Error('Invalid credentials. Use the demo account credentials shown on the welcome screen.');
  }

  const token = randomUUID();
  const now = new Date();

  return {
    user: createDemoUser(),
    rememberMe: request.rememberMe,
    token,
    createdAt: now.toISOString(),
    expiresAt: new Date(now.getTime() + 1000 * 60 * 60 * 24 * 30).toISOString(),
  };
}

export function login(request: LoginRequest): LoginResult {
  const session = createSession(request);
  if (!session.user) {
    throw new Error('Unable to create a desktop session.');
  }
  return {
    user: session.user,
    token: session.token,
    rememberMe: session.rememberMe,
  };
}

export async function clearLocalIdentityData(): Promise<void> {
  const userData = createUserDataPath('xelora-state.json');
  try {
    await fs.unlink(userData);
  } catch {
  }
}

export function getDemoCredentials(): { email: string; password: string } {
  return {
    email: DEMO_EMAIL,
    password: DEMO_PASSWORD,
  };
}
