'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';
import { Button } from '@/components/ui/button';
import { getSubscription, type SubscriptionSummary, type UsageSummary } from '@/services/billing';
import { getPlanByTier } from '@/data/plans';
import { formatDate } from '@/lib/utils';
import { cn } from '@/lib/utils';

function Meter({ label, used, limit, help }: { label: string; used: number; limit: number | 'unlimited'; help: string }) {
  const pct = typeof limit === 'number' && limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  return (
    <div className="rounded-xl border border-xelora-border bg-xelora-surface p-5">
      <p className="text-sm text-xelora-text-secondary">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-xelora-text">
        {used.toLocaleString()}
        <span className="text-sm font-normal text-xelora-text-muted"> / {typeof limit === 'number' ? limit.toLocaleString() : 'Unlimited'}</span>
      </p>
      {typeof limit === 'number' && (
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-xelora-surface-2" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
          <div className={cn('h-full rounded-full', pct >= 90 ? 'bg-xelora-error' : pct >= 75 ? 'bg-xelora-warning' : 'bg-xelora-green')} style={{ width: `${pct}%` }} />
        </div>
      )}
      <p className="mt-3 text-xs text-xelora-text-muted">{help}</p>
    </div>
  );
}

export default function UsagePage() {
  const [data, setData] = useState<{ subscription: SubscriptionSummary; usage: UsageSummary } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSubscription().then(setData).catch((err) => setError(err instanceof Error ? err.message : 'Could not load usage.'));
  }, []);

  if (error) return <StatePanel kind="error" title="Could not load usage" description={error} />;
  if (!data) return <StatePanel kind="loading" title="Loading usage" description="" />;

  const plan = getPlanByTier(data.subscription.planTier);
  const resets = data.usage.resetDate ? formatDate(data.usage.resetDate) : null;

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <DashboardPageHeader
        title="Usage"
        description={`You are on the ${plan.name} plan.${resets ? ` Usage resets on ${resets}.` : ''}`}
        actions={<Button variant="outline" asChild><Link href="/dashboard/billing/plans">Change plan</Link></Button>}
      />
      <div className="grid gap-4 md:grid-cols-2">
        <Meter label="AI actions" used={data.usage.aiActionsUsed} limit={data.usage.aiActionsLimit} help="Each new task you start counts as one. Quick answers and follow-ups in the same chat do not." />
        <Meter label="Workflow runs" used={data.usage.workflowRunsUsed} limit={data.usage.workflowRunsLimit} help="Each time you run a saved workflow counts as one run." />
      </div>
      <section className="rounded-xl border border-xelora-border bg-xelora-surface">
        <h2 className="border-b border-xelora-border px-5 py-3.5 text-sm font-semibold text-xelora-text">Plan limits</h2>
        <dl className="grid gap-x-8 gap-y-4 p-5 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {[
            ['Maximum file size', plan.limits.maxFileSizeMB === 'custom' ? 'Custom' : `${plan.limits.maxFileSizeMB} MB`],
            ['Saved workflows', String(plan.limits.savedWorkflows)],
            ['File storage', plan.limits.cloudStorageGB === 0 ? 'Not included' : `${plan.limits.cloudStorageGB} GB`],
            ['Connected devices', String(plan.limits.devices)],
            ['History kept', `${plan.limits.historyDays} days`],
            ['Team members', String(plan.limits.teamMembers)],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-xelora-text-secondary">{label}</dt>
              <dd className="mt-0.5 font-medium text-xelora-text">{value}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
