'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Check } from 'lucide-react';
import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import { Button } from '@/components/ui/button';
import { planHighlights, plans } from '@/data/plans';
import { site } from '@/lib/site';
import { cn } from '@/lib/utils';
import type { Plan } from '@/types';

type Limits = Plan['limits'];

function amount(value: number | string, suffix = '') {
  if (value === 'custom') return 'Custom';
  return `${Number(value).toLocaleString()}${suffix}`;
}

const rows: { label: string; value: (limits: Limits) => string }[] = [
  { label: 'AI actions per month', value: (l) => amount(l.aiActionsPerMonth) },
  { label: 'Workflow runs per month', value: (l) => amount(l.workflowRunsPerMonth) },
  { label: 'Maximum file size', value: (l) => amount(l.maxFileSizeMB, ' MB') },
  { label: 'Saved workflows', value: (l) => amount(l.savedWorkflows) },
  { label: 'File storage', value: (l) => (l.cloudStorageGB === 0 ? '—' : amount(l.cloudStorageGB, ' GB')) },
  { label: 'Connected devices', value: (l) => amount(l.devices) },
  { label: 'History kept', value: (l) => amount(l.historyDays, ' days') },
  { label: 'Team members', value: (l) => amount(l.teamMembers) },
  { label: 'Priority support', value: (l) => (l.prioritySupport ? 'Included' : '—') },
];

const included = [
  'Xelora Desktop for Windows',
  'Chat with web search and sources',
  'Plans and confirmation before big changes',
  'Verified results',
  'File version history',
  'Workflow templates',
];

const faqs = [
  { q: 'Can I change plans later?', a: 'Yes. Upgrade, downgrade or cancel from Billing in the app. Changes apply from your next billing period.' },
  { q: 'What counts as an AI action?', a: 'Each new task you start in Xelora counts as one AI action. Quick answers and follow-ups in the same conversation do not count. Usage is shown in the app and resets every billing period.' },
  { q: 'Is the desktop app extra?', a: 'No. Xelora Desktop is included in every plan.' },
  { q: 'What happens if I reach a limit?', a: 'Xelora tells you which limit was reached. You can wait for the next period or upgrade straight away.' },
];

export default function PricingPage() {
  const [annual, setAnnual] = useState(false);

  return (
    <>
      <MarketingNav />
      <main className="bg-white">
        <section className="mx-auto max-w-6xl px-4 pb-12 pt-20 text-center sm:px-6 lg:px-8">
          <p className="text-sm font-medium text-xelora-green">Pricing</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-xelora-text sm:text-5xl">Simple plans that grow with you</h1>
          <p className="mx-auto mt-5 max-w-xl text-lg text-xelora-text-secondary">
            Every account starts with a {site.trialDays}-day free trial. No credit card required.
          </p>
          <div className="mt-8 inline-flex rounded-lg border border-xelora-border bg-xelora-surface-2 p-1" role="group" aria-label="Billing period">
            {[false, true].map((option) => (
              <button
                key={String(option)}
                type="button"
                onClick={() => setAnnual(option)}
                aria-pressed={annual === option}
                className={cn(
                  'rounded-md px-4 py-1.5 text-sm font-medium transition-colors',
                  annual === option ? 'bg-white text-xelora-text shadow-sm' : 'text-xelora-text-secondary hover:text-xelora-text',
                )}
              >
                {option ? 'Yearly · save up to 25%' : 'Monthly'}
              </button>
            ))}
          </div>
        </section>

        <section className="mx-auto grid max-w-6xl gap-4 px-4 sm:px-6 md:grid-cols-2 lg:grid-cols-4 lg:px-8">
          {plans.map((plan) => {
            const featured = plan.tier === 'professional';
            const price = annual ? plan.annualPrice : plan.monthlyPrice;
            return (
              <div key={plan.tier} className={cn('flex flex-col rounded-2xl border p-6', featured ? 'border-xelora-green ring-1 ring-xelora-green' : 'border-xelora-border')}>
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-xelora-text">{plan.name}</h2>
                  {featured && <span className="rounded-full bg-xelora-success-bg px-2 py-0.5 text-[11px] font-medium text-xelora-green">Most popular</span>}
                </div>
                <p className="mt-4 text-4xl font-semibold tracking-tight text-xelora-text">
                  {price === null ? 'Custom' : price === 0 ? 'Free' : `$${price}`}
                </p>
                <p className="mt-1 h-5 text-xs text-xelora-text-muted">
                  {price ? `per month${annual ? ', billed yearly' : ''}` : plan.tier === 'trial' ? `for ${site.trialDays} days` : ''}
                </p>
                <p className="mt-4 min-h-10 text-sm text-xelora-text-secondary">{plan.description}</p>
                <Button className="mt-6 w-full" variant={featured ? 'default' : 'outline'} asChild>
                  <Link href={plan.tier === 'business' ? '/contact' : '/register'}>
                    {plan.tier === 'business' ? 'Contact us' : plan.tier === 'trial' ? 'Start free trial' : `Choose ${plan.name}`}
                  </Link>
                </Button>
                <ul className="mt-6 space-y-2 border-t border-xelora-border pt-6 text-sm text-xelora-text-secondary">
                  {planHighlights(plan).map((item) => (
                    <li key={item} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-xelora-green" />{item}</li>
                  ))}
                </ul>
              </div>
            );
          })}
        </section>

        <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-semibold tracking-tight text-xelora-text">Compare plans</h2>
          <div className="mt-8 overflow-x-auto rounded-2xl border border-xelora-border">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="bg-xelora-bg-main">
                <tr>
                  <th scope="col" className="px-5 py-3 font-medium text-xelora-text-secondary">Limits</th>
                  {plans.map((plan) => <th key={plan.tier} scope="col" className="px-5 py-3 font-semibold text-xelora-text">{plan.name}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-xelora-border">
                {rows.map((row) => (
                  <tr key={row.label}>
                    <th scope="row" className="px-5 py-3 font-normal text-xelora-text-secondary">{row.label}</th>
                    {plans.map((plan) => <td key={plan.tier} className="px-5 py-3 tabular-nums text-xelora-text">{row.value(plan.limits)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-8 rounded-2xl border border-xelora-border p-6">
            <h3 className="text-sm font-semibold text-xelora-text">Included in every plan</h3>
            <ul className="mt-4 grid gap-2 text-sm text-xelora-text-secondary sm:grid-cols-2 lg:grid-cols-3">
              {included.map((item) => <li key={item} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-xelora-green" />{item}</li>)}
            </ul>
          </div>
        </section>

        <section className="border-t border-xelora-border bg-xelora-bg-main">
          <div className="mx-auto max-w-3xl px-4 py-20 sm:px-6 lg:px-8">
            <h2 className="text-2xl font-semibold tracking-tight text-xelora-text">Billing questions</h2>
            <dl className="mt-8 space-y-6">
              {faqs.map(({ q, a }) => (
                <div key={q}>
                  <dt className="text-base font-medium text-xelora-text">{q}</dt>
                  <dd className="mt-2 text-sm leading-relaxed text-xelora-text-secondary">{a}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>
      </main>
      <MarketingFooter />
    </>
  );
}
