'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth-store';
import { AdminSidebar } from '@/components/admin/admin-sidebar';
import { AdminTopbar } from '@/components/admin/admin-topbar';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, initialize, user } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    initialize();
  }, [initialize]);

  useEffect(() => {
    if (!isLoading && (!isAuthenticated || !user?.isAdmin)) {
      router.push('/login');
    }
  }, [isLoading, isAuthenticated, router, user?.isAdmin]);

  if (isLoading) {
    return <div className="min-h-screen bg-xelora-bg-main" />;
  }

  if (!isAuthenticated || !user?.isAdmin) {
    return null;
  }

  return (
    <div className="flex min-h-screen bg-xelora-bg-main">
      <div className="hidden lg:block">
        <AdminSidebar pathname={pathname} />
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <AdminTopbar />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
