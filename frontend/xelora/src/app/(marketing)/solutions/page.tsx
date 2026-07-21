import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import { SectionHeading } from '@/components/site/section-heading';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { marketingSolutions } from '@/data/mock-marketing';

export default function SolutionsPage() {
  return (
    <>
      <MarketingNav />
      <main className="bg-xelora-bg-main">
        <section className="border-b border-xelora-border bg-white">
          <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <SectionHeading
              eyebrow="Solutions"
              title="Designed for the spreadsheet-heavy work people actually do"
              description="Xelora adapts to common operating teams, keeps the process visible, and leaves the final decision in human hands."
            />
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {marketingSolutions.map((solution) => (
              <Card key={solution.title} className="p-5">
                <h2 className="text-base font-semibold text-xelora-text">{solution.title}</h2>
                <p className="mt-2 text-sm text-xelora-text-secondary">{solution.description}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {solution.focus.map((item) => (
                    <Badge key={item} variant="outline">
                      {item}
                    </Badge>
                  ))}
                </div>
                <p className="mt-4 text-sm">
                  <span className="font-medium text-xelora-text">Outcome: </span>
                  <span className="text-xelora-text-secondary">{solution.outcome}</span>
                </p>
              </Card>
            ))}
          </div>
        </section>
      </main>
      <MarketingFooter />
    </>
  );
}
