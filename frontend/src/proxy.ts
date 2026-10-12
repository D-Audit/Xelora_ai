import { NextRequest, NextResponse } from 'next/server';

/**
 * Xelora's workspace runs only in Xelora Desktop. A regular browser asking
 * for it is sent to /open, which hands off to the app, so the workspace is
 * never served to a browser. Set NEXT_PUBLIC_ENABLE_WEB_APP=true to allow it
 * (local development). Electron puts "Electron/<version>" in its user agent.
 */
export function proxy(request: NextRequest) {
  if (process.env.NEXT_PUBLIC_ENABLE_WEB_APP === 'true') return NextResponse.next();
  if (/\bElectron\//.test(request.headers.get('user-agent') ?? '')) return NextResponse.next();

  const { pathname, search } = request.nextUrl;
  const target = new URL('/open', request.url);
  target.searchParams.set('path', pathname === '/onboarding' ? '/dashboard/agent' : pathname + search);
  return NextResponse.redirect(target);
}

export const config = {
  matcher: ['/dashboard/:path*', '/onboarding'],
};
