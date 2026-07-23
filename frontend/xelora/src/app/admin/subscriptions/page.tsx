'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';

interface AdminSubscription {
  id: string;
  userId: string;
  userEmail: string;
  planTier: string;
  billingCycle: string;
  status: string;
  currentPeriodEnd: string | null;
  cancelAtPeriodEnd: boolean;
}

export default function AdminSubscriptionsPage() {
  const [subs, setSubs] = useState<AdminSubscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/admin/subscriptions', { cache: 'no-store' })
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Could not load subscriptions.');
        setSubs(data.subscriptions);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load subscriptions.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <DashboardPageHeader eyebrow="Admin" title="Subscriptions" description="Live subscription inventory across all accounts." />
        <StatePanel kind="loading" title="Loading subscriptions" description="Fetching subscription data." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <DashboardPageHeader eyebrow="Admin" title="Subscriptions" description="Live subscription inventory across all accounts." />
        <StatePanel kind="empty" title="Could not load subscriptions" description={error} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <DashboardPageHeader eyebrow="Admin" title="Subscriptions" description="Live subscription inventory across all accounts." />
      <div className="space-y-3">
        {subs.map((sub) => (
          <Card key={sub.id} className="flex flex-wrap items-center justify-between gap-3 p-5">
            <div>
              <p className="text-sm font-semibold text-xelora-text capitalize">{sub.planTier}</p>
              <p className="text-sm text-xelora-text-secondary">{sub.userEmail} · {sub.billingCycle} billing</p>
              {sub.currentPeriodEnd && <p className="text-xs text-xelora-text-muted">Renews {sub.currentPeriodEnd.slice(0, 10)}</p>}
            </div>
            <div className="flex items-center gap-2">
              {sub.cancelAtPeriodEnd && <Badge variant="warning">Cancels at period end</Badge>}
              <Badge variant={sub.status === 'active' || sub.status === 'trialing' ? 'success' : 'default'}>{sub.status}</Badge>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
