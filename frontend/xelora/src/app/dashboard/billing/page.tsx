'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { CreditCard, Ban, ArrowRight, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { getSubscription, getInvoices, cancelSubscription, getPlans } from '@/services/billing';
import type { SubscriptionSummary, UsageSummary, InvoiceSummary, PlanSummary } from '@/services/billing';
import { formatCurrency, formatDate } from '@/lib/utils';

export default function BillingPage() {
  const [subscription, setSubscription] = useState<SubscriptionSummary | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [plan, setPlan] = useState<PlanSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [dialog, setDialog] = useState<'cancel' | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [subRes, invRes, plansRes] = await Promise.all([
          getSubscription(),
          getInvoices().catch(() => ({ invoices: [] })),
          getPlans(),
        ]);
        setSubscription(subRes.subscription);
        setUsage(subRes.usage);
        setInvoices(invRes.invoices);
        setPlan(plansRes.plans.find((p) => p.tier === subRes.subscription.planTier) ?? plansRes.plans[0]);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Could not load your subscription.');
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, []);

  const handleCancel = async () => {
    setIsSubmitting(true);
    try {
      const { subscription: updated } = await cancelSubscription(false);
      setSubscription(updated);
      toast.success('Your plan will be cancelled at the end of the current billing period.');
      setDialog(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not cancel your plan.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-xelora-text-muted" />
      </div>
    );
  }

  if (!subscription || !plan) {
    return (
      <Card className="p-6 text-center text-sm text-xelora-text-secondary">
        Could not load your subscription. Try refreshing, or check that the backend is running.
      </Card>
    );
  }

  const price = subscription.billingCycle === 'annual' ? plan.annualPrice : plan.monthlyPrice;

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Billing"
        title="Manage your subscription"
        description="Review your plan, usage reset date, and invoices."
        actions={
          <>
            <Button variant="outline" asChild>
              <Link href="/dashboard/billing/plans">Compare plans</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/dashboard/billing/invoices">View invoices</Link>
            </Button>
          </>
        }
      />

      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-xelora-text">{plan.name}</p>
            <p className="text-sm text-xelora-text-secondary">{plan.description}</p>
          </div>
          <div className="flex gap-2">
            <Badge variant={subscription.status === 'active' || subscription.status === 'trialing' ? 'success' : 'default'}>
              {subscription.status}
            </Badge>
            {subscription.cancelAtPeriodEnd && <Badge variant="default">Cancels at period end</Badge>}
          </div>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-4">
          {[
            { label: 'Renewal date', value: subscription.currentPeriodEnd ? formatDate(subscription.currentPeriodEnd) : '—' },
            { label: 'Current price', value: price != null ? `${formatCurrency(price)}/${subscription.billingCycle === 'annual' ? 'mo (billed yearly)' : 'mo'}` : 'Custom' },
            { label: 'Plan tier', value: subscription.planTier },
            { label: 'Invoices', value: `${invoices.length}` },
          ].map((item) => (
            <div key={item.label} className="rounded-lg border border-xelora-border bg-xelora-surface-2 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">{item.label}</p>
              <p className="mt-2 text-sm font-medium text-xelora-text">{item.value}</p>
            </div>
          ))}
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          <Button asChild>
            <Link href="/dashboard/billing/plans">
              <ArrowRight className="h-4 w-4" />
              Change plan
            </Link>
          </Button>
          {!subscription.cancelAtPeriodEnd && subscription.status !== 'cancelled' && (
            <Button variant="ghost" onClick={() => setDialog('cancel')} className="text-xelora-error">
              <Ban className="h-4 w-4" />
              Cancel plan
            </Button>
          )}
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="text-base font-semibold text-xelora-text">Usage this period</h2>
          <ul className="mt-3 space-y-2 text-sm text-xelora-text-secondary">
            <li>AI actions: {usage?.aiActionsUsed ?? 0} / {usage?.aiActionsLimit ?? '—'}</li>
            <li>Workflow runs: {usage?.workflowRunsUsed ?? 0} / {usage?.workflowRunsLimit ?? '—'}</li>
            <li>Cloud storage: {plan.limits.cloudStorageGB} GB included</li>
            <li>Devices: {plan.limits.devices}</li>
          </ul>
        </Card>
        <Card className="p-5">
          <h2 className="text-base font-semibold text-xelora-text">Recent invoices</h2>
          <div className="mt-3 space-y-3">
            {invoices.length === 0 && <p className="text-sm text-xelora-text-muted">No invoices yet.</p>}
            {invoices.slice(0, 2).map((invoice) => (
              <div key={invoice.id} className="flex items-center justify-between rounded-lg border border-xelora-border p-3">
                <div>
                  <p className="text-sm font-medium text-xelora-text">{invoice.description ?? 'Subscription'}</p>
                  <p className="text-xs text-xelora-text-muted">{invoice.issuedAt ? formatDate(invoice.issuedAt) : '—'}</p>
                </div>
                <p className="text-sm font-medium text-xelora-text">{formatCurrency(invoice.amount)}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Dialog open={dialog !== null} onOpenChange={() => setDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel plan</DialogTitle>
            <DialogDescription>
              Your plan stays active until the end of the current billing period, then moves to the free trial tier.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(null)}>Keep plan</Button>
            <Button onClick={handleCancel} disabled={isSubmitting} className="text-xelora-error">
              {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <CreditCard className="h-4 w-4" />}
              Confirm cancellation
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
