'use client';

import { useMemo, useState } from 'react';
import { Search, BookOpenText, FileText, Shapes, Sparkles } from 'lucide-react';
import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import { SectionHeading } from '@/components/site/section-heading';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { resourceItems } from '@/data/mock-marketing';

export default function ResourcesPage() {
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    return resourceItems.filter((item) => {
      const haystack = `${item.title} ${item.category} ${item.description} ${item.audience}`.toLowerCase();
      return haystack.includes(search.toLowerCase());
    });
  }, [search]);

  return (
    <>
      <MarketingNav />
      <main className="bg-xelora-bg-main">
        <section className="border-b border-xelora-border bg-white">
          <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <SectionHeading
              eyebrow="Resources"
              title="Practical help for people learning Xelora"
              description="Find tutorials, workflow guides, spreadsheet tips, and product updates in one calm, searchable place."
            />
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative w-full sm:max-w-sm">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-xelora-text-muted" />
              <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search resources" className="pl-9" />
            </div>
            <div className="flex flex-wrap gap-2">
              {['Help centre', 'Tutorials', 'Workflow guides', 'Spreadsheet tips'].map((label) => (
                <Badge key={label} variant="outline">
                  {label}
                </Badge>
              ))}
            </div>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((item) => (
              <Card key={item.title} className="p-5">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-xelora-surface-2">
                    {item.category === 'Help centre' ? <BookOpenText className="h-5 w-5 text-xelora-green" /> : item.category === 'Tutorials' ? <Sparkles className="h-5 w-5 text-xelora-info" /> : item.category === 'Workflow guides' ? <Shapes className="h-5 w-5 text-xelora-warning" /> : <FileText className="h-5 w-5 text-xelora-text-secondary" />}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-xelora-text">{item.title}</p>
                    <p className="text-xs text-xelora-text-muted">{item.category}</p>
                  </div>
                </div>
                <p className="mt-3 text-sm text-xelora-text-secondary">{item.description}</p>
                <p className="mt-4 text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Audience: {item.audience}</p>
              </Card>
            ))}
          </div>
        </section>
      </main>
      <MarketingFooter />
    </>
  );
}
