import { NextRequest, NextResponse } from 'next/server';
import { openHandoff } from '@/lib/desktop-handoff';
import { getOAuthOrigin } from '@/lib/oauth';
import { applySessionCookie } from '@/lib/session';

/** Loaded inside Xelora Desktop with the code from xelora://auth and the app's own secret. */
export async function GET(req: NextRequest) {
  const origin = getOAuthOrigin(req);
  const handoff = openHandoff(req.nextUrl.searchParams.get('code') ?? '', req.nextUrl.searchParams.get('secret') ?? '');
  if (!handoff) {
    return NextResponse.redirect(`${origin}/login?error=${encodeURIComponent('That sign-in link has expired. Please try again.')}`);
  }
  const response = NextResponse.redirect(`${origin}${handoff.isNewUser ? '/onboarding' : '/dashboard/agent'}`);
  return applySessionCookie(response, handoff.token, handoff.expiresAt);
}
