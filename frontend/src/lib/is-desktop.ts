import { useSyncExternalStore } from 'react';

/**
 * Detects whether the app is running inside the Xelora Desktop
 * Electron wrapper (desktop/), as opposed to a
 * regular browser tab.
 *
 * Relies on window.xeloraDesktop.isDesktopApp, which
 * desktop/preload.js exposes via contextBridge - see that
 * file. This is a UX signal only (which nav items/pages to show), not
 * a security boundary - nothing sensitive is gated by it, since
 * anyone could technically fake this in devtools, but there's nothing
 * to protect here: the underlying /task endpoint is still protected
 * by real auth and plan limits either way.
 */
export interface LocalAgentStatus {
  state: 'stopped' | 'starting' | 'running' | 'error' | 'unpaired' | 'unavailable';
  message: string;
  paired: boolean;
  userId: string | null;
  tokenId: number | null;
  apiUrl: string | null;
}

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
      /** Opens Google/Microsoft sign-in in the system browser (desktop/main.js). */
      signInWithBrowser?: (provider: 'google' | 'microsoft') => Promise<boolean>;
      /** Local agent that runs this user's tasks in Excel (desktop/agent.js). */
      agent?: {
        getStatus: () => Promise<LocalAgentStatus>;
        start: () => Promise<LocalAgentStatus>;
        pair: (details: { apiUrl: string; token: string; tokenId: number; userId: string }) => Promise<LocalAgentStatus>;
        unpair: () => Promise<LocalAgentStatus>;
        onChange: (callback: (status: LocalAgentStatus) => void) => () => void;
      };
    };
  }
}

export function isDesktopApp(): boolean {
  if (typeof window === 'undefined') return false;
  return Boolean(window.xeloraDesktop?.isDesktopApp || window.xelora);
}

const noSubscription = () => () => {};

/** React hook form of isDesktopApp(): false during server rendering, then the real value. */
export function useIsDesktop(): boolean {
  return useSyncExternalStore(noSubscription, isDesktopApp, () => false);
}
