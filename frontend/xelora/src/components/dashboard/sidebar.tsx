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
  LayoutDashboard, GitBranch, Files, LayoutTemplate, Settings,
  Users, ChevronLeft, X, Bot, Plus, History
} from 'lucide-react';
import { mockUsage } from '@/data/mock-usage';
import { getUsagePercentage } from '@/lib/utils';
import { isDesktopApp } from '@/lib/is-desktop';
import { useEffect, useState } from 'react';

const primaryItems = [
  { href: '/dashboard/agent', label: 'Chat', icon: Bot, desktopOnly: true },
  { href: '/dashboard', label: 'Overview', icon: LayoutDashboard, exact: true },
];

const workspaceItems = [
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

  const isActive = (href: string, exact = false) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + '/');

  return (
    <aside
      className={cn(
        'flex h-full flex-col border-r border-[#e8e8e4] bg-[#f7f7f5] text-xelora-text transition-all duration-200',
        collapsed ? 'w-16' : 'w-60'
      )}
      aria-label="Main navigation"
    >
      {/* Header */}
      <div className={cn('flex items-center px-4 py-4', collapsed ? 'justify-center' : 'justify-between')}>
        {!collapsed && <XeloraLogo size="sm" />}
        <button
          onClick={() => { toggleSidebarCollapsed(); setSidebarOpen(false); }}
          className="hidden lg:flex h-7 w-7 items-center justify-center rounded-md text-xelora-text-muted hover:bg-black/5 hover:text-xelora-text transition-colors"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <ChevronLeft className={cn('h-4 w-4 transition-transform duration-200', collapsed && 'rotate-180')} />
        </button>
        <button
          onClick={() => setSidebarOpen(false)}
          className="lg:hidden h-7 w-7 flex items-center justify-center rounded-md text-xelora-text-muted hover:bg-black/5 hover:text-xelora-text transition-colors"
          aria-label="Close menu"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2 py-2" aria-label="Dashboard navigation">
        {!collapsed && (
          <Link href="/dashboard/agent" className="mb-4 flex items-center justify-center gap-2 rounded-lg bg-xelora-deep-green px-3 py-2.5 text-sm font-medium text-white transition-colors hover:bg-xelora-green">
            <Plus className="h-4 w-4" /> New task
          </Link>
        )}
        {collapsed && <Link href="/dashboard/agent" aria-label="New task" className="mb-4 flex h-10 items-center justify-center rounded-lg bg-xelora-deep-green text-white"><Plus className="h-4 w-4" /></Link>}
        <ul role="list" className="space-y-0.5">
          {primaryItems.filter((item) => !item.desktopOnly || showDesktopItems).map(({ href, label, icon: Icon, exact }) => {
            const active = isActive(href, exact);
            return (
              <li key={href}>
                <Link
                  href={href}
                  onClick={() => setSidebarOpen(false)}
                  className={cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors duration-150',
                    active
                      ? 'bg-white text-xelora-text font-medium shadow-sm'
                      : 'text-xelora-text-secondary hover:bg-black/[0.045] hover:text-xelora-text'
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
        {!collapsed && <p className="mb-2 mt-6 px-3 text-[11px] font-medium uppercase tracking-[0.08em] text-xelora-text-muted">Workspace</p>}
        <ul role="list" className="space-y-0.5">
          {workspaceItems.map(({ href, label, icon: Icon }) => {
            const active = isActive(href);
            return <li key={href}><Link href={href} onClick={() => setSidebarOpen(false)} className={cn('flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors', active ? 'bg-white font-medium text-xelora-text shadow-sm' : 'text-xelora-text-secondary hover:bg-black/[0.045] hover:text-xelora-text')}><Icon className="h-4 w-4 shrink-0" />{!collapsed && <span>{label}</span>}</Link></li>;
          })}
        </ul>
      </nav>

      {/* Usage bar */}
      {!collapsed && (
        <div className="mx-2 mb-2 rounded-xl border border-xelora-border bg-white px-3 py-3">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-xelora-text-secondary">AI actions</span>
            <span className="text-xs text-xelora-text-muted">{mockUsage.aiActionsUsed} / {mockUsage.aiActionsLimit}</span>
          </div>
          <Progress value={aiPct} className="h-1.5 bg-xelora-surface-2" indicatorClassName="bg-xelora-green" />
          <div className="mt-3 flex items-center justify-between">
            <Badge variant="outline" className="border-xelora-border text-xelora-text-secondary text-[10px]">
              {user?.plan ?? 'Professional'}
            </Badge>
            <Link href="/dashboard/billing/plans" className="text-[10px] font-medium text-xelora-green hover:underline">
              Upgrade
            </Link>
          </div>
        </div>
      )}
      <div className="border-t border-[#e8e8e4] p-2">
        <Link href="/dashboard/settings" className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-xelora-text-secondary hover:bg-black/[0.045] hover:text-xelora-text"><Settings className="h-4 w-4" />{!collapsed && 'Settings'}</Link>
        <Link href="/dashboard/history" className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-xelora-text-secondary hover:bg-black/[0.045] hover:text-xelora-text"><History className="h-4 w-4" />{!collapsed && 'Task history'}</Link>
      </div>
    </aside>
  );
}
