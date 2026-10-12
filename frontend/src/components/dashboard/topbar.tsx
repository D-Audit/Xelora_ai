'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Bell, Menu } from 'lucide-react';
import { useUIStore } from '@/stores/ui-store';
import { getNotifications } from '@/services/workspace';

export function Topbar() {
  const { toggleSidebar } = useUIStore();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    getNotifications()
      .then((items) => setUnread(items.filter((item) => !item.isRead).length))
      .catch(() => setUnread(0));
  }, []);

  return (
    <header className="sticky top-0 z-30 flex h-12 shrink-0 items-center gap-2 border-b border-xelora-border bg-xelora-bg-main/90 px-4 backdrop-blur sm:px-6">
      <button
        onClick={toggleSidebar}
        className="flex h-8 w-8 items-center justify-center rounded-lg text-xelora-text-secondary transition-colors hover:bg-xelora-surface-2 lg:hidden"
        aria-label="Open navigation"
      >
        <Menu className="h-4 w-4" />
      </button>
      <div className="ml-auto">
        <Link
          href="/dashboard/notifications"
          className="relative flex h-8 w-8 items-center justify-center rounded-lg text-xelora-text-secondary transition-colors hover:bg-xelora-surface-2 hover:text-xelora-text"
          aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}
        >
          <Bell className="h-4 w-4" />
          {unread > 0 && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-xelora-green ring-2 ring-xelora-bg-main" aria-hidden="true" />}
        </Link>
      </div>
    </header>
  );
}
