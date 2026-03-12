'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth-store';

export default function DesktopLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, initialize } = useAuthStore();
  const router = useRouter();

  useEffect(() => { initialize(); }, [initialize]);
  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.push('/login');
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-xelora-nav flex items-center justify-center">
        <div className="h-5 w-5 rounded-full border-2 border-xelora-bright-green border-t-transparent animate-spin" />
      </div>
    );
  }
  if (!isAuthenticated) return null;
  return <>{children}</>;
}
