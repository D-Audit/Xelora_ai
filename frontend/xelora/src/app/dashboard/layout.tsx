'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { usePathname } from 'next/navigation';
import { useAuthStore } from '@/stores/auth-store';
import { useUIStore } from '@/stores/ui-store';
import { Sidebar } from '@/components/dashboard/sidebar';
import { Topbar } from '@/components/dashboard/topbar';
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
      router.push('/login');
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-xelora-bg-main flex items-center justify-center">
        <div className="h-6 w-6 rounded-full border-2 border-xelora-green border-t-transparent animate-spin" aria-label="Loading" />
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="flex h-screen overflow-hidden bg-xelora-bg-main">
      {/* Desktop sidebar */}
      <div className="hidden lg:flex flex-shrink-0">
        <Sidebar collapsed={sidebarCollapsed} />
      </div>

      {/* Mobile sidebar drawer */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden flex">
          <div
            className="absolute inset-0 bg-xelora-black/40"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
          <div className="relative w-60 flex-shrink-0">
            <Sidebar collapsed={false} />
          </div>
        </div>
      )}

      {/* Main area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {!isChatWorkspace && <Topbar />}
        <main
          className={cn('flex-1 overflow-y-auto', isChatWorkspace ? 'bg-xelora-surface' : 'bg-xelora-bg-main p-4 sm:p-6')}
          id="main-content"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
