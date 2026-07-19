'use client';

import { useMemo, useState } from 'react';
import { Search, Filter, ArrowRight, Layers3, Workflow, ShieldCheck } from 'lucide-react';
import Link from 'next/link';
import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { SectionHeading } from '@/components/site/section-heading';
import { StatePanel } from '@/components/site/state-panel';
import { marketingFeatures } from '@/data/mock-marketing';

const filters = [
  { id: 'all', label: 'All surfaces' },
  { id: 'web dashboard', label: 'Web dashboard' },
  { id: 'desktop app', label: 'Desktop app' },
  { id: 'both', label: 'Both' },
] as const;

export default function FeaturesPage() {
  const [search, setSearch] = useState('');
  const [surface, setSurface] = useState<(typeof filters)[number]['id']>('all');
  const [loading] = useState(false);

  const filtered = useMemo(() => {
    return marketingFeatures.filter((feature) => {
      const matchesSurface = surface === 'all' || feature.surface === surface;
      const haystack = `${feature.title} ${feature.summary} ${feature.whoBenefits} ${feature.useCase}`.toLowerCase();
      const matchesSearch = haystack.includes(search.toLowerCase());
      return matchesSurface && matchesSearch;
    });
  }, [search, surface]);

  return (
    <>
      <MarketingNav />
      <main className="bg-xelora-bg-main">
        <section className="border-b border-xelora-border bg-white">
          <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
            <div className="grid gap-10 lg:grid-cols-[1.2fr_.8fr] lg:items-start">
              <div className="max-w-2xl">
                <SectionHeading
                  eyebrow="Product"
                  title="A calm, controlled way to automate spreadsheet work"
                  description="Xelora combines an AI assistant, step-by-step workflow planning, and reversible spreadsheet actions so teams can work faster without losing oversight."
                />
                <div className="mt-8 flex flex-wrap gap-3">
                  <Button asChild>
                    <Link href="/register">
                      Start Free Trial <ArrowRight className="h-4 w-4" />
                    </Link>
                  </Button>
                  <Button variant="outline" asChild>
                    <Link href="/how-it-works">See how workflows run</Link>
                  </Button>
                </div>
              </div>

              <div className="grid gap-3">
                <Card className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-md bg-xelora-success-bg">
                      <Workflow className="h-5 w-5 text-xelora-success" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-xelora-text">Workflow planning</p>
                      <p className="text-xs text-xelora-text-secondary">Every change is visible before it is applied.</p>
                    </div>
                  </div>
                </Card>
                <Card className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-md bg-xelora-info-bg">
                      <Layers3 className="h-5 w-5 text-xelora-info" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-xelora-text">Reusable workflows</p>
                      <p className="text-xs text-xelora-text-secondary">Save templates once and reuse them across files.</p>
                    </div>
                  </div>
                </Card>
                <Card className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-md bg-xelora-warning-bg">
                      <ShieldCheck className="h-5 w-5 text-xelora-warning" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-xelora-text">Approval controls</p>
                      <p className="text-xs text-xelora-text-secondary">Pause at key points and let a human approve the next step.</p>
                    </div>
                  </div>
                </Card>
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <SectionHeading
              eyebrow="Capabilities"
              title="Everything Xelora does, in plain language"
              description="Filter by where the feature lives and scan for the part of the product that matters to you."
            />
            <div className="flex flex-col gap-3 sm:flex-row">
              <div className="relative w-full sm:w-72">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-xelora-text-muted" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search features"
                  className="pl-9"
                  aria-label="Search features"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                {filters.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setSurface(item.id)}
                    className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-xs font-medium transition-colors ${
                      surface === item.id
                        ? 'border-xelora-green bg-xelora-success-bg text-xelora-success'
                        : 'border-xelora-border bg-white text-xelora-text-secondary hover:bg-xelora-surface-2'
                    }`}
                  >
                    <Filter className="h-3.5 w-3.5" />
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-8">
            {loading ? (
              <StatePanel
                kind="loading"
                title="Loading feature library"
                description="We are preparing the feature breakdown and usage examples."
              />
            ) : filtered.length === 0 ? (
              <StatePanel
                kind="empty"
                title="No features match those filters"
                description="Try a broader search term or switch to another product surface."
                actionLabel="Reset filters"
                onAction={() => {
                  setSearch('');
                  setSurface('all');
                }}
              />
            ) : (
              <div className="grid gap-4 lg:grid-cols-2">
                {filtered.map((feature) => (
                  <Card key={feature.title} className="p-5">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="default">{feature.surface}</Badge>
                      <Badge variant="outline">Feature</Badge>
                    </div>
                    <h3 className="mt-3 text-base font-semibold text-xelora-text">{feature.title}</h3>
                    <p className="mt-2 text-sm text-xelora-text-secondary">{feature.summary}</p>
                    <dl className="mt-4 space-y-3 text-sm">
                      <div>
                        <dt className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Who benefits</dt>
                        <dd className="mt-1 text-xelora-text-secondary">{feature.whoBenefits}</dd>
                      </div>
                      <div>
                        <dt className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Use case</dt>
                        <dd className="mt-1 text-xelora-text-secondary">{feature.useCase}</dd>
                      </div>
                    </dl>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </section>
      </main>
      <MarketingFooter />
    </>
  );
}
