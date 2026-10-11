import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import { SectionHeading } from '@/components/site/section-heading';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { securityTopics } from '@/data/mock-marketing';

export default function SecurityPage() {
  return (
    <>
      <MarketingNav />
      <main className="bg-xelora-bg-main">
        <section className="border-b border-xelora-border bg-white">
          <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <SectionHeading
              eyebrow="Security"
              title="Built so users can see where data lives and what happens to it"
              description="Xelora is designed around user-controlled processing, clear retention settings, and transparent AI context."
            />
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {securityTopics.map((topic) => (
              <Card key={topic.title} className="p-5">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-base font-semibold text-xelora-text">{topic.title}</h2>
                  <Badge variant="outline">Transparent</Badge>
                </div>
                <p className="mt-2 text-sm text-xelora-text-secondary">{topic.summary}</p>
                <ul className="mt-4 space-y-2 text-sm text-xelora-text-secondary">
                  {topic.details.map((detail) => (
                    <li key={detail} className="flex gap-2">
                      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-xelora-green" />
                      <span>{detail}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        </section>
      </main>
      <MarketingFooter />
    </>
  );
}
