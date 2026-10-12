import { NextRequest } from 'next/server';
import { relayJson } from '@/lib/relay';

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  return relayJson('/auth/change-password', {
    auth: true,
    body: { current_password: body.currentPassword ?? null, new_password: body.newPassword },
  });
}
