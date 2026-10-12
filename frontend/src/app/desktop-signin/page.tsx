'use client';

import { Suspense, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { CircleCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { XeloraLogo } from '@/components/ui/xelora-logo';

/** Shown in the browser after a sign-in that was started from Xelora Desktop. */
export default function DesktopSignInPage() {
  return <Suspense fallback={null}><DesktopSignIn /></Suspense>;
}

function DesktopSignIn() {
  const code = useSearchParams().get('code');
  const link = code ? `xelora://auth?code=${encodeURIComponent(code)}` : null;

  useEffect(() => {
    if (link) window.location.href = link;
  }, [link]);

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center bg-xelora-bg-main px-4">
      <XeloraLogo size="md" />
      <div className="mt-8 w-full max-w-sm rounded-2xl border border-xelora-border bg-white p-8 text-center shadow-sm">
        {link ? (
          <>
            <CircleCheck className="mx-auto h-8 w-8 text-xelora-green" strokeWidth={1.75} />
            <h1 className="mt-4 text-lg font-semibold text-xelora-text">You are signed in</h1>
            <p className="mt-2 text-sm text-xelora-text-secondary">
              Return to Xelora Desktop to continue. If it did not open, select the button below.
            </p>
            <Button className="mt-6 w-full" asChild>
              <a href={link}>Open Xelora Desktop</a>
            </Button>
            <p className="mt-4 text-xs text-xelora-text-muted">You can close this tab afterwards.</p>
          </>
        ) : (
          <>
            <h1 className="text-lg font-semibold text-xelora-text">This link is incomplete</h1>
            <p className="mt-2 text-sm text-xelora-text-secondary">Start signing in again from Xelora Desktop.</p>
            <Button className="mt-6 w-full" variant="outline" asChild><Link href="/login">Go to sign in</Link></Button>
          </>
        )}
      </div>
    </main>
  );
}
