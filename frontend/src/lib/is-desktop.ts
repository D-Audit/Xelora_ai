/**
 * Detects whether the app is running inside the Xelora Desktop
 * Electron wrapper (frontend/xelora-desktop/), as opposed to a
 * regular browser tab.
 *
 * Relies on window.xeloraDesktop.isDesktopApp, which
 * xelora-desktop/preload.js exposes via contextBridge - see that
 * file. This is a UX signal only (which nav items/pages to show), not
 * a security boundary - nothing sensitive is gated by it, since
 * anyone could technically fake this in devtools, but there's nothing
 * to protect here: the underlying /task endpoint is still protected
 * by real auth and plan limits either way.
 */
declare global {
  interface Window {
    xelora?: {
      getAppInfo?: () => Promise<unknown>;
    };
    xeloraDesktop?: {
      platform: string;
      version: string;
      isDesktopApp: boolean;
      reload: () => void;
      setFloatingMode: (enabled: boolean) => Promise<boolean>;
      getFloatingMode: () => Promise<boolean>;
      onFloatingModeChange: (callback: (enabled: boolean) => void) => () => void;
    };
  }
}

export function isDesktopApp(): boolean {
  if (typeof window === 'undefined') return false;
  return Boolean(window.xeloraDesktop?.isDesktopApp || window.xelora);
}
