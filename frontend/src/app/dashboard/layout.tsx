'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { usePathname } from 'next/navigation';
import { useAuthStore } from '@/stores/auth-store';
import { useUIStore } from '@/stores/ui-store';
import { Sidebar } from '@/components/dashboard/sidebar';
import { Topbar } from '@/components/dashboard/topbar';
import { LocalAgentBridge } from '@/components/desktop/local-agent';
import { cn } from '@/lib/utils';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, initialize } = useAuthStore();
  const { sidebarOpen, sidebarCollapsed, setSidebarOpen } = useUIStore();
  const router = useRouter();
  const pathname = usePathname();
  const isChatWorkspace = pathname === '/dashboard/agent';

  useEffect(() => {
    initialize();
  }, [initialize]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-xelora-bg-main">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-xelora-border-strong border-t-xelora-text" aria-label="Loading" />
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="flex h-screen overflow-hidden bg-xelora-bg-main">
      <LocalAgentBridge />
      <div className="hidden lg:flex flex-shrink-0">
        <Sidebar collapsed={sidebarCollapsed} />
      </div>

      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden flex">
          <div
            className="absolute inset-0 bg-xelora-black/40"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
          <div className="relative flex-shrink-0">
            <Sidebar collapsed={false} />
          </div>
        </div>
      )}

      <div className="flex flex-1 flex-col overflow-hidden">
        {!isChatWorkspace && <Topbar />}
        <main
          className={cn('flex-1 overflow-y-auto', isChatWorkspace ? 'bg-xelora-surface' : 'bg-xelora-bg-main px-4 py-6 sm:px-8 sm:py-8')}
          id="main-content"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
