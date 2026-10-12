import type { Metadata } from 'next';
import Link from 'next/link';
import { Mail, LifeBuoy, Building2 } from 'lucide-react';
import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import { site } from '@/lib/site';

export const metadata: Metadata = { title: 'Contact', description: `Get in touch with the ${site.name} team.` };

const channels = [
  { icon: LifeBuoy, title: 'Product help', text: 'Questions about using Xelora, your account or billing.', action: { label: site.contactEmail, href: `mailto:${site.contactEmail}?subject=Help%20with%20Xelora` } },
  { icon: Building2, title: 'Business plan', text: 'Custom limits, more team members and dedicated support for your organisation.', action: { label: 'Talk to us', href: `mailto:${site.contactEmail}?subject=Xelora%20Business%20plan` } },
  { icon: Mail, title: 'Privacy and security', text: 'Data requests, account deletion and security reports.', action: { label: site.privacyEmail, href: `mailto:${site.privacyEmail}?subject=Privacy%20request` } },
];

export default function ContactPage() {
  return (
    <>
      <MarketingNav />
      <main className="bg-white">
        <div className="mx-auto max-w-5xl px-4 py-20 sm:px-6 lg:px-8">
          <p className="text-sm font-medium text-xelora-green">Contact</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-xelora-text">How can we help?</h1>
          <p className="mt-4 max-w-xl text-lg text-xelora-text-secondary">We usually reply within one business day.</p>
          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {channels.map(({ icon: Icon, title, text, action }) => (
              <div key={title} className="flex flex-col rounded-2xl border border-xelora-border p-6">
                <Icon className="h-5 w-5 text-xelora-text" strokeWidth={1.75} aria-hidden="true" />
                <h2 className="mt-4 text-base font-semibold text-xelora-text">{title}</h2>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-xelora-text-secondary">{text}</p>
                <a href={action.href} className="mt-5 text-sm font-medium text-xelora-green hover:underline">{action.label}</a>
              </div>
            ))}
          </div>
          <p className="mt-10 text-sm text-xelora-text-secondary">
            Already a customer? <Link href="/login" className="text-xelora-green hover:underline">Sign in</Link> and use Help in the app.
          </p>
        </div>
      </main>
      <MarketingFooter />
    </>
  );
}
