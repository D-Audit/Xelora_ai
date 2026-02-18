'use client';

import { useRouter } from 'next/navigation';
import { LogOut, Shield, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuthStore } from '@/stores/auth-store';

export function AdminTopbar() {
  const router = useRouter();
  const logout = useAuthStore((state) => state.logout);

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-xelora-border bg-white px-4 sm:px-6">
      <div className="flex items-center gap-2 text-sm font-medium text-xelora-text">
        <Shield className="h-4 w-4 text-xelora-green" />
        Admin console
      </div>
      <div className="flex items-center gap-2">
        <div className="hidden items-center gap-2 rounded-md border border-xelora-border bg-xelora-surface-2 px-3 py-1.5 md:flex">
          <Search className="h-4 w-4 text-xelora-text-muted" />
          <span className="text-sm text-xelora-text-muted">Search admin data</span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            logout();
            router.push('/login');
          }}
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </Button>
      </div>
    </header>
  );
}
