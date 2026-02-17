import Link from 'next/link';
import { cn } from '@/lib/utils';

const items = [
  { href: '/admin', label: 'Overview' },
  { href: '/admin/users', label: 'Users' },
  { href: '/admin/plans', label: 'Plans' },
  { href: '/admin/subscriptions', label: 'Subscriptions' },
  { href: '/admin/usage', label: 'Usage' },
  { href: '/admin/templates', label: 'Templates' },
  { href: '/admin/releases', label: 'Desktop releases' },
  { href: '/admin/system', label: 'System' },
];

export function AdminSidebar({ pathname }: { pathname: string }) {
  return (
    <aside className="flex h-full w-64 flex-col border-r border-xelora-border bg-xelora-black text-white">
      <div className="border-b border-white/10 px-5 py-4">
        <p className="text-sm font-semibold">Xelora Admin</p>
        <p className="text-xs text-white/60">Separated control surface</p>
      </div>
      <nav className="flex-1 px-3 py-3">
        <ul className="space-y-1">
          {items.map((item) => {
            const active = pathname === item.href;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    'block rounded-md px-3 py-2 text-sm transition-colors',
                    active ? 'bg-white/10 text-white' : 'text-white/70 hover:bg-white/5 hover:text-white'
                  )}
                >
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
