import { after } from 'next/server';
import { wakeBackend } from '@/lib/backend';

/** POST /api/warm: sign-in pages call this on load so a sleeping backend boots early. */
export async function POST() {
  after(wakeBackend);
  return new Response(null, { status: 204 });
}
