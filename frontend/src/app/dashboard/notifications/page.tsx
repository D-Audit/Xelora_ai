'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Bell, CheckCheck } from 'lucide-react';
import { toast } from 'sonner';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';
import { getNotifications, markNotificationRead, markAllNotificationsRead } from '@/services/workspace';
import type { NotificationItem } from '@/services/workspace';
import { formatRelativeTime } from '@/lib/utils';

const priorityVariant: Record<string, 'default' | 'warning' | 'error'> = {
  low: 'default',
  medium: 'warning',
  high: 'error',
};

export default function NotificationsPage() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    getNotifications()
      .then(setItems)
      .catch((err) => toast.error(err instanceof Error ? err.message : 'Could not load notifications.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleRead = async (n: NotificationItem) => {
    if (n.isRead) return;
    setItems((current) => current.map((i) => (i.id === n.id ? { ...i, isRead: true } : i)));
    try {
      await markNotificationRead(n.id);
    } catch {
    }
  };

  const handleReadAll = async () => {
    setItems((current) => current.map((i) => ({ ...i, isRead: true })));
    try {
      await markAllNotificationsRead();
      toast.success('All notifications marked as read.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not update notifications.');
    }
  };

  const unreadCount = items.filter((i) => !i.isRead).length;

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Notifications"
        title="Notifications"
        description={unreadCount > 0 ? `${unreadCount} unread` : 'You are all caught up.'}
        actions={
          unreadCount > 0 ? (
            <Button variant="outline" onClick={handleReadAll}>
              <CheckCheck className="h-4 w-4" /> Mark all as read
            </Button>
          ) : undefined
        }
      />

      {loading ? (
        <StatePanel kind="loading" title="Loading notifications" description="Fetching your notifications." />
      ) : items.length === 0 ? (
        <StatePanel kind="empty" title="No notifications yet" description="You'll see workflow, billing, and account updates here." />
      ) : (
        <div className="space-y-2">
          {items.map((n) => (
            <Card
              key={n.id}
              className={`flex items-start gap-3 p-4 ${!n.isRead ? 'border-xelora-green/40 bg-xelora-success-bg/30' : ''}`}
              onClick={() => handleRead(n)}
            >
              <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-xelora-surface-2">
                <Bell className="h-4 w-4 text-xelora-text-secondary" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-xelora-text">{n.title}</p>
                  {n.priority !== 'low' && <Badge variant={priorityVariant[n.priority] ?? 'default'}>{n.priority}</Badge>}
                  {!n.isRead && <span className="h-1.5 w-1.5 rounded-full bg-xelora-green" />}
                </div>
                <p className="mt-1 text-sm text-xelora-text-secondary">{n.message}</p>
                <div className="mt-2 flex items-center gap-3">
                  <p className="text-xs text-xelora-text-muted">{n.createdAt ? formatRelativeTime(n.createdAt) : ''}</p>
                  {n.actionUrl && n.actionLabel && (
                    <Link href={n.actionUrl} className="text-xs font-medium text-xelora-green hover:underline">
                      {n.actionLabel}
                    </Link>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
