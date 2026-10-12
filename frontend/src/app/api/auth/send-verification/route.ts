import { relayJson } from '@/lib/relay';

export async function POST() {
  return relayJson('/auth/send-verification', { auth: true });
}
