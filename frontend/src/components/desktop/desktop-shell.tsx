'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';
import { useIsDesktop } from '@/lib/is-desktop';

/** Website-only pages that make no sense inside the installed app. */
const WEBSITE_ONLY = new Set(['/', '/download']);

/**
 * Inside Xelora Desktop: keeps the window's title bar in the app theme and
 * sends the user to their workspace instead of the marketing site.
 */
export function DesktopShell() {
  const desktop = useIsDesktop();
  const pathname = usePathname();
  const router = useRouter();
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    if (desktop && (resolvedTheme === 'dark' || resolvedTheme === 'light')) {
      void window.xeloraDesktop?.setTheme?.(resolvedTheme);
    }
  }, [desktop, resolvedTheme]);

  useEffect(() => {
    if (desktop && WEBSITE_ONLY.has(pathname)) router.replace('/dashboard/agent');
  }, [desktop, pathname, router]);

  return null;
}
