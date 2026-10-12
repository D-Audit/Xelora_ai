import { NextRequest } from 'next/server';
import { relayJson } from '@/lib/relay';

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  return relayJson('/auth/forgot-password', { body: { email: body.email } });
}
