import Link from 'next/link';
import { Button } from '@/components/ui/button';

export function CtaSection() {
  return (
    <section className="py-24 bg-xelora-deep-green" aria-labelledby="cta-heading">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
        <h2 id="cta-heading" className="text-3xl font-semibold text-white sm:text-4xl">
          Spend less time repeating spreadsheet work.
        </h2>
        <p className="mt-4 text-base text-white/70 max-w-xl mx-auto leading-relaxed">
          14-day free trial. No credit card required. Cancel any time.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Button variant="bright" size="xl" asChild>
            <Link href="/register">Start Free Trial</Link>
          </Button>
          <Button size="xl" className="bg-white/10 text-white border border-white/20 hover:bg-white/20" asChild>
            <Link href="/pricing">View Pricing</Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
