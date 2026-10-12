import { NextRequest } from 'next/server';
import { finishOAuth } from '@/lib/oauth-flow';

export async function GET(req: NextRequest) {
  return finishOAuth(req, 'microsoft');
}
