import { NextRequest } from 'next/server';
import { startOAuth } from '@/lib/oauth-flow';

export async function GET(req: NextRequest) {
  return startOAuth(req, 'microsoft');
}
