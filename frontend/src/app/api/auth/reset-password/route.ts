import { NextRequest } from 'next/server';
import { relayJson } from '@/lib/relay';

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  return relayJson('/auth/reset-password', { body: { token: body.token, password: body.password } });
}
