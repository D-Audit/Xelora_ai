'use client';

import Link from 'next/link';
import { useAuthStore } from '@/stores/auth-store';
import { useUIStore } from '@/stores/ui-store';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Menu, Bell, Search } from 'lucide-react';
import { mockNotifications } from '@/data/mock-notifications';

export function Topbar() {
  const { user } = useAuthStore();
  const { toggleSidebar } = useUIStore();
  const unreadCount = mockNotifications.filter((notification) => !notification.isRead).length;

  const planLabel = user?.plan === 'professional' ? 'Professional' :
    user?.plan === 'starter' ? 'Starter' :
      user?.plan === 'business' ? 'Business' : 'Trial';

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-xelora-border bg-white px-4 sm:px-6">
      <button
        onClick={toggleSidebar}
        className="flex h-8 w-8 items-center justify-center rounded text-xelora-text-secondary transition-colors hover:bg-xelora-surface-2 lg:hidden"
        aria-label="Open navigation"
      >
        <Menu className="h-4 w-4" />
      </button>

      <div className="hidden max-w-xs flex-1 sm:flex">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-xelora-text-muted" aria-hidden="true" />
          <input
            type="search"
            placeholder="Search workflows, filesâ€¦"
            className="h-8 w-full rounded-md border border-xelora-border bg-xelora-surface-2 pl-9 pr-3 text-sm text-xelora-text placeholder:text-xelora-text-muted focus:outline-none focus:ring-2 focus:ring-xelora-border-focus"
            aria-label="Search"
          />
        </div>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <Badge variant="success" className="hidden text-xs sm:flex">{planLabel}</Badge>
        <Button variant="ghost" size="icon" className="relative" asChild>
          <Link href="/dashboard/notifications" aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}>
            <Bell className="h-4 w-4 text-xelora-text-secondary" />
            {unreadCount > 0 && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-xelora-error" aria-hidden="true" />}
          </Link>
        </Button>
      </div>
    </header>
  );
}
