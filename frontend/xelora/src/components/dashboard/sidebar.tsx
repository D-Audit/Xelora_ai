'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useUIStore } from '@/stores/ui-store';
import { useAuthStore } from '@/stores/auth-store';
import { XeloraLogo } from '@/components/ui/xelora-logo';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import {
  LayoutDashboard, GitBranch, Files, LayoutTemplate,
  Users, ChevronLeft, X, Bot
} from 'lucide-react';
import { mockUsage } from '@/data/mock-usage';
import { getUsagePercentage } from '@/lib/utils';
import { isDesktopApp } from '@/lib/is-desktop';
import { useEffect, useState } from 'react';

const navItems = [
  { href: '/dashboard', label: 'Overview', icon: LayoutDashboard, exact: true },
  { href: '/dashboard/agent', label: 'AI Agent', icon: Bot, desktopOnly: true },
  { href: '/dashboard/workflows', label: 'Workflows', icon: GitBranch },
  { href: '/dashboard/files', label: 'Files', icon: Files },
  { href: '/dashboard/templates', label: 'Templates', icon: LayoutTemplate },
  { href: '/dashboard/team', label: 'Team', icon: Users },
];

interface SidebarProps {
  collapsed?: boolean;
}

export function Sidebar({ collapsed = false }: SidebarProps) {
  const pathname = usePathname();
  const { toggleSidebarCollapsed, setSidebarOpen } = useUIStore();
  const user = useAuthStore(s => s.user);
  const aiPct = getUsagePercentage(mockUsage.aiActionsUsed, mockUsage.aiActionsLimit);

  // Starts false to match server-rendered HTML (avoids a hydration
  // mismatch), then flips true on mount if we're inside the desktop
  // app - see src/lib/is-desktop.ts.
  const [showDesktopItems, setShowDesktopItems] = useState(false);
  useEffect(() => setShowDesktopItems(isDesktopApp()), []);

  const visibleNavItems = navItems.filter((item) => !item.desktopOnly || showDesktopItems);

  const isActive = (href: string, exact = false) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + '/');

  return (
    <aside
      className={cn(
        'flex h-full flex-col bg-xelora-nav text-white transition-all duration-200',
        collapsed ? 'w-16' : 'w-60'
      )}
      aria-label="Main navigation"
    >
      {/* Header */}
      <div className={cn('flex items-center border-b border-white/10 px-4 py-4', collapsed ? 'justify-center' : 'justify-between')}>
        {!collapsed && <XeloraLogo variant="light" size="sm" />}
        <button
          onClick={() => { toggleSidebarCollapsed(); setSidebarOpen(false); }}
          className="hidden lg:flex h-7 w-7 items-center justify-center rounded text-white/50 hover:text-white hover:bg-white/10 transition-colors"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <ChevronLeft className={cn('h-4 w-4 transition-transform duration-200', collapsed && 'rotate-180')} />
        </button>
        <button
          onClick={() => setSidebarOpen(false)}
          className="lg:hidden h-7 w-7 flex items-center justify-center rounded text-white/50 hover:text-white hover:bg-white/10 transition-colors"
          aria-label="Close menu"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2" aria-label="Dashboard navigation">
        <ul role="list" className="space-y-0.5">
          {visibleNavItems.map(({ href, label, icon: Icon, exact }) => {
            const active = isActive(href, exact);
            return (
              <li key={href}>
                <Link
                  href={href}
                  onClick={() => setSidebarOpen(false)}
                  className={cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors duration-150',
                    active
                      ? 'bg-white/10 text-white font-medium'
                      : 'text-white/60 hover:bg-white/8 hover:text-white'
                  )}
                  aria-current={active ? 'page' : undefined}
                >
                  <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {!collapsed && <span>{label}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Usage bar */}
      {!collapsed && (
        <div className="border-t border-white/10 px-4 py-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-white/50">AI actions</span>
            <span className="text-xs text-white/70">{mockUsage.aiActionsUsed} / {mockUsage.aiActionsLimit}</span>
          </div>
          <Progress value={aiPct} className="h-1.5 bg-white/10" indicatorClassName="bg-xelora-bright-green" />
          <div className="mt-3 flex items-center justify-between">
            <Badge variant="outline" className="border-white/20 text-white/60 text-[10px]">
              {user?.plan ?? 'Professional'}
            </Badge>
            <Link href="/dashboard/billing" className="text-[10px] text-xelora-bright-green hover:underline">
              Manage plan
            </Link>
          </div>
        </div>
      )}
    </aside>
  );
}
