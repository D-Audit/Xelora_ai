import Link from 'next/link';
import { XeloraLogo } from '@/components/ui/xelora-logo';
import { site } from '@/lib/site';

const footerColumns = [
  {
    heading: 'Product',
    links: [
      { label: 'Features', href: '/#product' },
      { label: 'How it works', href: '/#how-it-works' },
      { label: 'Pricing', href: '/pricing' },
      { label: 'Download for Windows', href: '/download' },
    ],
  },
  {
    heading: 'Trust',
    links: [
      { label: 'Security', href: '/security' },
      { label: 'Status', href: '/status' },
    ],
  },
  {
    heading: 'Company',
    links: [
      { label: 'Contact', href: '/contact' },
      { label: 'Sign in', href: '/login' },
    ],
  },
  {
    heading: 'Legal',
    links: [
      { label: 'Terms of Service', href: '/terms' },
      { label: 'Privacy Policy', href: '/privacy' },
      { label: 'Acceptable Use', href: '/acceptable-use' },
      { label: 'Cookie Policy', href: '/cookies' },
    ],
  },
];

export function MarketingFooter() {
  return (
    <footer className="border-t border-xelora-border bg-white">
      <div className="mx-auto max-w-6xl px-4 pb-10 pt-14 sm:px-6 lg:px-8">
        <div className="grid gap-10 lg:grid-cols-[1.4fr_repeat(4,1fr)]">
          <div>
            <XeloraLogo size="sm" />
            <p className="mt-3 max-w-xs text-sm leading-relaxed text-xelora-text-secondary">{site.tagline}</p>
          </div>
          {footerColumns.map((column) => (
            <div key={column.heading}>
              <h3 className="text-xs font-semibold text-xelora-text">{column.heading}</h3>
              <ul className="mt-3 space-y-2.5">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="text-sm text-xelora-text-secondary transition-colors hover:text-xelora-text">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-12 flex flex-col gap-2 border-t border-xelora-border pt-6 text-xs text-xelora-text-muted sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} {site.legalName}. All rights reserved.</p>
          <p>Microsoft and Excel are trademarks of the Microsoft group of companies. Xelora is not affiliated with Microsoft.</p>
        </div>
      </div>
    </footer>
  );
}
