import Link from 'next/link';
import { XeloraLogo } from '@/components/ui/xelora-logo';

const footerColumns = [
  {
    heading: 'Product',
    links: [
      { label: 'Features', href: '/features' },
      { label: 'How It Works', href: '/how-it-works' },
      { label: 'Pricing', href: '/pricing' },
      { label: 'Security', href: '/security' },
      { label: 'Download', href: '/download' },
      { label: 'Resources', href: '/resources' },
    ],
  },
  {
    heading: 'Solutions',
    links: [{ label: 'All solutions', href: '/solutions' }],
  },
  {
    heading: 'Resources',
    links: [
      { label: 'Help Centre', href: '/dashboard/help' },
      { label: 'Template Gallery', href: '/dashboard/templates' },
      { label: 'Usage', href: '/dashboard/usage' },
      { label: 'Workflows', href: '/dashboard/workflows' },
    ],
  },
  {
    heading: 'Company',
    links: [
      { label: 'Contact', href: '/contact' },
      { label: 'Status', href: '/status' },
    ],
  },
  {
    heading: 'Legal',
    links: [
      { label: 'Privacy Policy', href: '/privacy' },
      { label: 'Terms of Service', href: '/terms' },
      { label: 'Security', href: '/security' },
    ],
  },
];

export function MarketingFooter() {
  return (
    <footer className="bg-xelora-black text-white">
      <div className="mx-auto max-w-7xl px-4 pb-12 pt-16 sm:px-6 lg:px-8">
        <div className="mb-12">
          <XeloraLogo variant="light" size="md" />
          <p className="mt-3 max-w-xs text-sm leading-relaxed text-white/60">
            Automate spreadsheets. Stay in control.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-8 sm:grid-cols-3 lg:grid-cols-5">
          {footerColumns.map((column) => (
            <div key={column.heading}>
              <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-white/40">
                {column.heading}
              </h3>
              <ul className="space-y-2.5">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-sm text-white/70 transition-colors duration-150 hover:text-white"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-white/10">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-white/40">© 2026 Xelora. All rights reserved.</p>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/20 px-3 py-1 text-xs font-medium text-white/60 self-start sm:self-auto">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-xelora-bright-green" aria-hidden="true" />
              Xelora Web
            </span>
            <div className="flex items-center gap-4">
              <Link href="/download" className="text-sm text-white/40 transition-colors duration-150 hover:text-white">
                Download
              </Link>
              <Link href="/status" className="text-sm text-white/40 transition-colors duration-150 hover:text-white">
                Status
              </Link>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
