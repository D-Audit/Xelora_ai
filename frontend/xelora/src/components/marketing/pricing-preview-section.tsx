import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Check } from 'lucide-react';
import { mockPlans } from '@/data/mock-plans';

const highlights: Record<string, string[]> = {
  trial: ['30 AI actions', '5 workflow runs', '5 MB file limit', '14 days free'],
  starter: ['300 AI actions/mo', '50 workflow runs', '2 GB cloud storage', '2 devices'],
  professional: ['1,500 AI actions/mo', '300 workflow runs', '20 GB cloud storage', 'Batch processing'],
  business: ['Custom AI usage', 'Unlimited workflows', 'Managed devices', 'API access'],
};

export function PricingPreviewSection() {
  return (
    <section className="py-20 bg-white border-b border-xelora-border" aria-labelledby="pricing-preview-heading">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl mb-12">
          <p className="text-sm font-medium text-xelora-green uppercase tracking-wide mb-3">Pricing</p>
          <h2 id="pricing-preview-heading" className="text-3xl font-semibold text-xelora-text leading-tight">
            Start free. Scale as you need.
          </h2>
        </div>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {mockPlans.map(plan => (
            <div
              key={plan.id}
              className={`rounded-lg border p-6 relative ${plan.isPopular ? 'border-xelora-green ring-1 ring-xelora-green' : 'border-xelora-border'}`}
            >
              {plan.isPopular && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-xelora-green text-white text-xs font-semibold px-3 py-1">
                  Most popular
                </span>
              )}
              <h3 className="text-base font-semibold text-xelora-text mb-1">{plan.name}</h3>
              <div className="mb-4">
                {plan.monthlyPrice === null ? (
                  <span className="text-2xl font-bold text-xelora-text">Custom</span>
                ) : plan.monthlyPrice === 0 ? (
                  <span className="text-2xl font-bold text-xelora-text">Free</span>
                ) : (
                  <>
                    <span className="text-2xl font-bold text-xelora-text">${plan.monthlyPrice}</span>
                    <span className="text-sm text-xelora-text-muted">/mo</span>
                  </>
                )}
              </div>
              <ul className="space-y-2 mb-5">
                {(highlights[plan.tier] ?? []).map(item => (
                  <li key={item} className="flex items-center gap-2 text-sm text-xelora-text-secondary">
                    <Check className="h-3.5 w-3.5 text-xelora-green shrink-0" aria-hidden="true" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-8 flex flex-wrap gap-3">
          <Button variant="bright" size="lg" asChild>
            <Link href="/register">Start Free Trial</Link>
          </Button>
          <Button variant="outline" size="lg" asChild>
            <Link href="/pricing">View full pricing</Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
