'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { CircleCheck, Download, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { XeloraLogo } from '@/components/ui/xelora-logo';
import { useAuthStore } from '@/stores/auth-store';

/** Only same-site paths are passed on to the app. */
export function safeAppPath(path: string | null | undefined): string {
  return path && path.startsWith('/') && !path.startsWith('//') && !path.includes('\\') ? path : '/dashboard/agent';
}

function openDesktopApp(path: string) {
  window.location.href = `xelora://open?path=${encodeURIComponent(safeAppPath(path))}`;
}

/**
 * Where a browser lands instead of the workspace, e.g. right after signing in
 * or signing up on the website. Like other desktop apps, it hands off to
 * Xelora Desktop through the xelora:// link (the browser asks to open the
 * app) and offers the installer to people who do not have it yet.
 *
 * `welcome` is for a brand-new account: the app is most likely not installed,
 * so downloading comes first and the app is not launched automatically.
 */
export function OpenInDesktop({ path, welcome = false }: { path: string; welcome?: boolean }) {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, initialize, logout } = useAuthStore();

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    if (!welcome) openDesktopApp(path);
  }, [path, welcome]);

  const firstName = user?.name?.split(' ')[0];
  const signedIn = !isLoading && isAuthenticated;

  const openButton = (
    <Button size="lg" variant={welcome ? 'outline' : 'default'} className="w-full" onClick={() => openDesktopApp(path)}>
      <ExternalLink className="h-4 w-4" /> Open Xelora Desktop
    </Button>
  );
  const downloadButton = (
    <Button size="lg" variant={welcome ? 'default' : 'outline'} className="w-full" asChild>
      <a href="/api/download/windows"><Download className="h-4 w-4" /> Download for Windows</a>
    </Button>
  );

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center bg-xelora-bg-main px-4 py-12">
      <Link href="/" aria-label="Xelora home"><XeloraLogo size="md" /></Link>
      <div className="mt-8 w-full max-w-md rounded-2xl border border-xelora-border bg-xelora-surface p-8 text-center shadow-sm">
        <CircleCheck className="mx-auto h-9 w-9 text-xelora-green" strokeWidth={1.75} aria-hidden="true" />
        <h1 className="mt-4 text-2xl font-semibold tracking-tight text-xelora-text">
          {signedIn ? `You're all set${firstName ? `, ${firstName}` : ''}` : 'Continue in Xelora Desktop'}
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-xelora-text-secondary">
          {welcome
            ? 'Your account is ready. Xelora works in Excel on your PC, so install the desktop app and sign in with this account to start.'
            : 'Xelora works in Excel on your PC, so your workspace lives in the desktop app. If your browser asks, choose Open Xelora.'}
        </p>

        <div className="mt-6 flex flex-col gap-3">
          {welcome ? downloadButton : openButton}
          <p className="pt-2 text-xs text-xelora-text-muted">{welcome ? 'Already installed?' : "Don't have the app yet?"}</p>
          {welcome ? openButton : downloadButton}
        </div>

        <p className="mt-6 text-xs text-xelora-text-muted">Windows 10 or 11 with Microsoft Excel. Sign in to the app with the same account.</p>
      </div>

      {signedIn && (
        <p className="mt-6 text-xs text-xelora-text-muted">
          Signed in as {user?.email}.{' '}
          <button
            type="button"
            className="font-medium text-xelora-text-secondary underline hover:text-xelora-text"
            onClick={async () => { await logout(); router.push('/'); }}
          >
            Sign out
          </button>
        </p>
      )}
    </main>
  );
}
