'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Check, Minus, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';
import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import { SectionHeading } from '@/components/site/section-heading';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { mockPlans } from '@/data/mock-plans';
import { formatCurrency } from '@/lib/utils';

const comparisonRows = [
  { label: 'AI actions per month', trial: '30', starter: '300', professional: '1,500', business: 'Custom' },
  { label: 'Workflow runs per month', trial: '5', starter: '50', professional: '300', business: 'Custom' },
  { label: 'Maximum file size', trial: '5 MB', starter: '25 MB', professional: '100 MB', business: 'Custom' },
  { label: 'Saved workflows', trial: '2', starter: '10', professional: 'Unlimited', business: 'Unlimited' },
  { label: 'Cloud storage', trial: 'None', starter: '2 GB', professional: '20 GB', business: 'Custom' },
  { label: 'Devices', trial: '1', starter: '2', professional: '3', business: 'Managed' },
  { label: 'Batch processing', trial: false, starter: false, professional: true, business: true },
  { label: 'API access', trial: false, starter: false, professional: false, business: true },
  { label: 'Role permissions', trial: false, starter: false, professional: false, business: true },
  { label: 'Audit history', trial: false, starter: false, professional: false, business: true },
];

const pricingFaqs = [
  {
    q: 'Can I change plans later?',
    a: 'Yes. You can upgrade, downgrade, or switch billing cycles from the billing section in the dashboard.',
  },
  {
    q: 'Do I need to pay for the desktop app separately?',
    a: 'No. Xelora Desktop is included with every plan. The difference is the amount of usage and team features included.',
  },
  {
    q: 'What happens when I hit a limit?',
    a: 'The app explains which limit was reached and what you can do next, such as waiting for a reset or upgrading the plan.',
  },
];

export default function PricingPage() {
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('monthly');
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);

  const plans = useMemo(
    () =>
      mockPlans.map((plan) => ({
        ...plan,
        price: billingCycle === 'annual' ? plan.annualPrice : plan.monthlyPrice,
      })),
    [billingCycle]
  );

  const handleCheckout = async () => {
    await new Promise((resolve) => setTimeout(resolve, 900));
    toast.success('Mock checkout completed. No payment was taken.');
    setSelectedPlan(null);
  };

  return (
    <>
      <MarketingNav />
      <main className="bg-xelora-bg-main">
        <section className="border-b border-xelora-border bg-white">
          <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <SectionHeading
              eyebrow="Pricing"
              title="Choose a plan that matches how much spreadsheet work you want to automate"
              description="Start with the trial, then move into the plan that fits your file sizes, usage, and team needs."
              align="center"
            />
            <div className="mt-8 flex justify-center gap-2 rounded-lg border border-xelora-border bg-xelora-surface-2 p-1">
              <button
                type="button"
                onClick={() => setBillingCycle('monthly')}
                className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                  billingCycle === 'monthly' ? 'bg-white text-xelora-text shadow-sm' : 'text-xelora-text-secondary'
                }`}
              >
                Monthly
              </button>
              <button
                type="button"
                onClick={() => setBillingCycle('annual')}
                className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                  billingCycle === 'annual' ? 'bg-white text-xelora-text shadow-sm' : 'text-xelora-text-secondary'
                }`}
              >
                Annual
                <Badge variant="success" className="ml-2 text-[10px]">
                  Save 20%
                </Badge>
              </button>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-4 lg:grid-cols-4">
            {plans.map((plan) => (
              <Card key={plan.id} className={`relative p-5 ${plan.isPopular ? 'border-xelora-green ring-1 ring-xelora-green' : ''}`}>
                {plan.isPopular ? (
                  <Badge variant="green" className="absolute -top-3 left-1/2 -translate-x-1/2">
                    Most popular
                  </Badge>
                ) : null}
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold text-xelora-text">{plan.name}</h2>
                    <p className="mt-1 text-sm text-xelora-text-secondary">{plan.description}</p>
                  </div>
                  <Badge variant={plan.tier === 'trial' ? 'info' : 'outline'}>{plan.tier}</Badge>
                </div>
                <div className="mt-5">
                  {plan.price === null ? (
                    <p className="text-3xl font-semibold text-xelora-text">Custom</p>
                  ) : plan.price === 0 ? (
                    <div>
                      <p className="text-3xl font-semibold text-xelora-text">Free</p>
                      <p className="text-sm text-xelora-text-muted">14-day trial</p>
                    </div>
                  ) : (
                    <div>
                      <p className="text-3xl font-semibold text-xelora-text">
                        {formatCurrency(plan.price * (billingCycle === 'annual' ? 10 : 1))}
                      </p>
                      <p className="text-sm text-xelora-text-muted">
                        {billingCycle === 'annual' ? 'billed annually' : 'per month'}
                      </p>
                    </div>
                  )}
                </div>
                <ul className="mt-5 space-y-2 text-sm text-xelora-text-secondary">
                  <li>{plan.limits.aiActionsPerMonth} AI actions</li>
                  <li>{plan.limits.workflowRunsPerMonth} workflow runs</li>
                  <li>{plan.limits.maxFileSizeMB} MB max file</li>
                  <li>{plan.limits.devices} device{plan.limits.devices === 1 ? '' : 's'}</li>
                </ul>
                <div className="mt-6">
                  <Button
                    className="w-full"
                    variant={plan.isPopular ? 'bright' : 'outline'}
                    onClick={() => setSelectedPlan(plan.name)}
                  >
                    {plan.tier === 'trial' ? 'Start free trial' : `Choose ${plan.name}`}
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </section>

        <section className="border-y border-xelora-border bg-white">
          <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
            <SectionHeading
              eyebrow="Plan comparison"
              title="See the main limits and features side by side"
              description="The table below is intentionally readable on desktop and scrollable on smaller screens."
            />
            <div className="mt-8 overflow-x-auto rounded-xl border border-xelora-border">
              <table className="w-full text-sm">
                <thead className="bg-xelora-surface-2">
                  <tr className="border-b border-xelora-border">
                    <th className="px-5 py-3 text-left font-medium text-xelora-text-secondary">Feature</th>
                    {['Trial', 'Starter', 'Professional', 'Business'].map((heading) => (
                      <th key={heading} className="px-4 py-3 text-center font-medium text-xelora-text">
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-xelora-border bg-white">
                  {comparisonRows.map((row) => (
                    <tr key={row.label}>
                      <td className="px-5 py-3 text-xelora-text-secondary">{row.label}</td>
                      {(['trial', 'starter', 'professional', 'business'] as const).map((tier) => (
                        <td key={tier} className="px-4 py-3 text-center">
                          {typeof row[tier] === 'boolean' ? (
                            row[tier] ? (
                              <Check className="mx-auto h-4 w-4 text-xelora-success" />
                            ) : (
                              <Minus className="mx-auto h-4 w-4 text-xelora-border-strong" />
                            )
                          ) : (
                            <span className="font-medium text-xelora-text">{row[tier]}</span>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-4 lg:grid-cols-[1fr_.8fr]">
            <Card className="p-5">
              <h2 className="text-base font-semibold text-xelora-text">Additional usage explanation</h2>
              <p className="mt-2 text-sm text-xelora-text-secondary">
                If you need more AI actions, workflow runs, or storage, the dashboard explains what was consumed and when the next reset occurs. Business plans can extend limits and add managed workspaces.
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-xelora-border bg-xelora-surface-2 p-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Free trial</p>
                  <p className="mt-1 text-sm text-xelora-text-secondary">14 days, 30 AI actions, 5 workflow runs.</p>
                </div>
                <div className="rounded-lg border border-xelora-border bg-xelora-surface-2 p-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Upgrade path</p>
                  <p className="mt-1 text-sm text-xelora-text-secondary">Upgrade in the billing area without reinstalling anything.</p>
                </div>
              </div>
            </Card>

            <Card className="p-5">
              <h2 className="text-base font-semibold text-xelora-text">Contact sales</h2>
              <p className="mt-2 text-sm text-xelora-text-secondary">
                Need a larger rollout, custom retention, or managed devices? The Business plan is built for that.
              </p>
              <Button className="mt-4 w-full" asChild>
                <Link href="/contact">
                  Contact Sales <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </Card>
          </div>
        </section>

        <section className="border-t border-xelora-border bg-white">
          <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
            <SectionHeading eyebrow="FAQ" title="Pricing questions, answered simply" />
            <div className="mt-6 grid gap-4 lg:grid-cols-3">
              {pricingFaqs.map((faq) => (
                <Card key={faq.q} className="p-5">
                  <h3 className="text-sm font-semibold text-xelora-text">{faq.q}</h3>
                  <p className="mt-2 text-sm text-xelora-text-secondary">{faq.a}</p>
                </Card>
              ))}
            </div>
          </div>
        </section>
      </main>
      <MarketingFooter />

      <Dialog open={selectedPlan !== null} onOpenChange={() => setSelectedPlan(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Mock checkout</DialogTitle>
            <DialogDescription>
              This is a frontend simulation for {selectedPlan ?? 'the selected'} plan. No payment details are collected.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedPlan(null)}>
              Cancel
            </Button>
            <Button onClick={handleCheckout}>Continue to checkout</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
