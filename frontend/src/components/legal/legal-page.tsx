import Link from 'next/link';
import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import { site } from '@/lib/site';

export interface LegalSection {
  id: string;
  title: string;
  body: React.ReactNode;
}

const legalLinks = [
  { href: '/terms', label: 'Terms of Service' },
  { href: '/privacy', label: 'Privacy Policy' },
  { href: '/acceptable-use', label: 'Acceptable Use Policy' },
  { href: '/cookies', label: 'Cookie Policy' },
];

/** Shared layout for the legal pages: title, contents, numbered sections. */
export function LegalPage({ title, intro, sections, current }: {
  title: string;
  intro: React.ReactNode;
  sections: LegalSection[];
  current: string;
}) {
  return (
    <>
      <MarketingNav />
      <main className="bg-white">
        <div className="mx-auto grid max-w-6xl gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[220px_1fr] lg:px-8 lg:py-20">
          <aside className="lg:sticky lg:top-24 lg:self-start">
            <nav aria-label="Legal documents">
              <p className="text-xs font-semibold uppercase tracking-wide text-xelora-text-muted">Legal</p>
              <ul className="mt-3 space-y-1">
                {legalLinks.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      aria-current={current === link.href ? 'page' : undefined}
                      className={current === link.href
                        ? 'block rounded-md bg-xelora-surface-2 px-3 py-1.5 text-sm font-medium text-xelora-text'
                        : 'block rounded-md px-3 py-1.5 text-sm text-xelora-text-secondary hover:text-xelora-text'}
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
            <nav aria-label="On this page" className="mt-8 hidden lg:block">
              <p className="text-xs font-semibold uppercase tracking-wide text-xelora-text-muted">On this page</p>
              <ol className="mt-3 space-y-1.5">
                {sections.map((section, index) => (
                  <li key={section.id}>
                    <a href={`#${section.id}`} className="block text-[13px] leading-snug text-xelora-text-secondary hover:text-xelora-text">
                      {index + 1}. {section.title}
                    </a>
                  </li>
                ))}
              </ol>
            </nav>
          </aside>

          <article className="max-w-3xl">
            <h1 className="text-4xl font-semibold tracking-tight text-xelora-text">{title}</h1>
            <p className="mt-3 text-sm text-xelora-text-muted">Last updated {site.legalUpdated}</p>
            <div className="mt-8 text-[15px] leading-relaxed text-xelora-text-secondary">{intro}</div>
            <div className="mt-12 space-y-12">
              {sections.map((section, index) => (
                <section key={section.id} id={section.id} className="scroll-mt-24">
                  <h2 className="text-xl font-semibold text-xelora-text">{index + 1}. {section.title}</h2>
                  <div className="legal-body mt-4 space-y-4 text-[15px] leading-relaxed text-xelora-text-secondary">{section.body}</div>
                </section>
              ))}
            </div>
            <div className="mt-16 rounded-2xl border border-xelora-border bg-xelora-bg-main p-6 text-sm text-xelora-text-secondary">
              Questions about this document? Email{' '}
              <a href={`mailto:${site.contactEmail}`} className="text-xelora-green hover:underline">{site.contactEmail}</a>
              {site.address ? <> or write to {site.legalName}, {site.address}</> : null}.
            </div>
          </article>
        </div>
      </main>
      <MarketingFooter />
    </>
  );
}

/** A bulleted list styled for legal text. */
export function Bullets({ items }: { items: React.ReactNode[] }) {
  return (
    <ul className="space-y-2">
      {items.map((item, index) => (
        <li key={index} className="flex gap-3">
          <span className="mt-2.5 h-1 w-1 shrink-0 rounded-full bg-xelora-text-muted" aria-hidden="true" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}
