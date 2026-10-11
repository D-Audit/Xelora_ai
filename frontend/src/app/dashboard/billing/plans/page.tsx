'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Check, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { getPlans, getSubscription, startCheckout } from '@/services/billing';
import type { PlanSummary } from '@/services/billing';

export default function BillingPlansPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [currentTier, setCurrentTier] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [pendingTier, setPendingTier] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [plansRes, subRes] = await Promise.all([getPlans(), getSubscription().catch(() => null)]);
        setPlans(plansRes.plans);
        if (subRes) setCurrentTier(subRes.subscription.planTier);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Could not load plans.');
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, []);

  const choosePlan = async (tier: string) => {
    if (tier === 'business') {
      router.push('/contact');
      return;
    }
    setPendingTier(tier);
    try {
      const result = await startCheckout(tier, 'monthly');
      if (result.checkout_url) {
        // eslint-disable-next-line no-restricted-globals -- external redirect to
        window.location.href = result.checkout_url;
        return;
      }
      toast.success(`Switched to the ${tier} plan.`);
      router.push('/dashboard/billing');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not start checkout.');
    } finally {
      setPendingTier(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-xelora-text-muted" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Billing"
        title="Compare plans"
        description="Pick the plan that fits - limits are enforced on every account, not just shown here."
        actions={<Button asChild variant="outline"><Link href="/dashboard/billing">Back to billing</Link></Button>}
      />
      <div className="grid gap-4 lg:grid-cols-4">
        {plans.map((plan) => {
          const isCurrent = plan.tier === currentTier;
          return (
            <Card key={plan.tier} className="p-5">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold text-xelora-text">{plan.name}</h2>
                <Badge variant={isCurrent ? 'success' : 'outline'}>{isCurrent ? 'Current' : plan.tier}</Badge>
              </div>
              <p className="mt-1 text-2xl font-semibold text-xelora-text">
                {plan.monthlyPrice != null ? `$${plan.monthlyPrice}` : 'Custom'}
                {plan.monthlyPrice != null && <span className="text-sm font-normal text-xelora-text-muted">/mo</span>}
              </p>
              <ul className="mt-4 space-y-2 text-sm text-xelora-text-secondary">
                <li>{plan.limits.aiActionsPerMonth} AI actions</li>
                <li>{plan.limits.workflowRunsPerMonth} workflow runs</li>
                <li>{plan.limits.maxFileSizeMB} MB maximum file</li>
                <li>{plan.limits.devices} device{plan.limits.devices === 1 ? '' : 's'}</li>
              </ul>
              <Button
                className="mt-5 w-full"
                disabled={isCurrent || pendingTier === plan.tier}
                onClick={() => choosePlan(plan.tier)}
              >
                {pendingTier === plan.tier && <Loader2 className="h-4 w-4 animate-spin" />}
                {isCurrent ? 'Current plan' : plan.tier === 'business' ? 'Contact sales' : 'Choose plan'}
              </Button>
            </Card>
          );
        })}
      </div>
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-xelora-surface-2">
              <tr className="border-b border-xelora-border text-left">
                <th className="px-5 py-3 text-xelora-text-secondary">Feature</th>
                {plans.map((p) => (
                  <th key={p.tier} className="px-4 py-3 text-center text-xelora-text-secondary">{p.name}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-xelora-border bg-white">
              {[
                { key: 'batchProcessing', label: 'Batch processing' },
                { key: 'apiAccess', label: 'API access' },
                { key: 'prioritySupport', label: 'Priority support' },
              ].map((feature) => (
                <tr key={feature.key}>
                  <td className="px-5 py-3 text-xelora-text-secondary">{feature.label}</td>
                  {plans.map((p) => (
                    <td key={p.tier} className="px-4 py-3 text-center">
                      {p.limits[feature.key as keyof PlanSummary['limits']] ? (
                        <Check className="mx-auto h-4 w-4 text-xelora-success" />
                      ) : (
                        <span className="text-xelora-text-muted">—</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
