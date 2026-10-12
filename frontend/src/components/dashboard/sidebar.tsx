'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { toast } from 'sonner';
import {
  Activity, Bell, ChevronsUpDown, CircleHelp, CreditCard, Download, Files, History, LayoutTemplate, Loader2, LogOut,
  MessageSquare, MonitorSmartphone, MoreHorizontal, PanelLeftClose, PanelLeftOpen, Settings, SquarePen, Trash2,
  Users, Workflow,
} from 'lucide-react';
import { cn, getInitials } from '@/lib/utils';
import { useUIStore } from '@/stores/ui-store';
import { useAuthStore } from '@/stores/auth-store';
import { XeloraLogo } from '@/components/ui/xelora-logo';
import { useIsDesktop } from '@/lib/is-desktop';
import { deleteChat, listChats } from '@/services/agent';
import type { ChatSummary } from '@/services/agent';
import { getSubscription, type UsageSummary } from '@/services/billing';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

const navItems = [
  { href: '/dashboard/agent', label: 'Chat', icon: MessageSquare },
  { href: '/dashboard/files', label: 'Files', icon: Files },
  { href: '/dashboard/workflows', label: 'Workflows', icon: Workflow },
  { href: '/dashboard/templates', label: 'Templates', icon: LayoutTemplate },
  { href: '/dashboard/history', label: 'Task history', icon: History },
];

const PLAN_LABEL: Record<string, string> = { trial: 'Free trial', starter: 'Starter', professional: 'Professional', business: 'Business' };

export function Sidebar({ collapsed = false }: { collapsed?: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toggleSidebarCollapsed, setSidebarOpen } = useUIStore();
  const { user, logout } = useAuthStore();
  const [chats, setChats] = useState<ChatSummary[] | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const desktop = useIsDesktop();

  useEffect(() => {
    if (collapsed) return;
    const load = () => listChats().then(setChats).catch(() => setChats([]));
    load();
    window.addEventListener('xelora:chats-updated', load);
    return () => window.removeEventListener('xelora:chats-updated', load);
  }, [collapsed]);

  useEffect(() => {
    getSubscription().then((data) => setUsage(data.usage)).catch(() => setUsage(null));
  }, []);

  const close = () => setSidebarOpen(false);
  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);
  const activeChat = pathname === '/dashboard/agent' ? searchParams.get('chat') : null;

  const removeChat = async (chat: ChatSummary) => {
    try {
      await deleteChat(chat.id);
      if (activeChat === String(chat.id)) router.replace('/dashboard/agent?new=1');
      window.dispatchEvent(new Event('xelora:chats-updated'));
      toast.success('Conversation deleted.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not delete this conversation.');
    }
  };

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  const usageLimit = usage && typeof usage.aiActionsLimit === 'number' ? usage.aiActionsLimit : null;
  const usagePct = usage && usageLimit ? Math.min(100, Math.round((usage.aiActionsUsed / usageLimit) * 100)) : 0;
  const plan = user?.plan ?? 'trial';

  return (
    <aside
      className={cn(
        'flex h-full flex-col border-r border-xelora-border bg-xelora-bg-main text-xelora-text transition-[width] duration-200',
        collapsed ? 'w-[60px]' : 'w-[264px]'
      )}
      aria-label="Main navigation"
    >
      <div className={cn('flex h-14 shrink-0 items-center px-3', collapsed ? 'justify-center' : 'justify-between pl-4')}>
        {!collapsed && (
          <Link href="/dashboard/agent" onClick={close} aria-label="Xelora chat">
            <XeloraLogo size="sm" />
          </Link>
        )}
        <button
          onClick={() => { toggleSidebarCollapsed(); close(); }}
          className="hidden h-8 w-8 items-center justify-center rounded-lg text-xelora-text-muted transition-colors hover:bg-xelora-surface-2 hover:text-xelora-text lg:flex"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </button>
      </div>

      <div className="px-2.5">
        <Link
          href="/dashboard/agent?new=1"
          onClick={close}
          title="New chat"
          className={cn(
            'flex h-9 items-center gap-2.5 rounded-lg border border-xelora-border bg-xelora-surface text-sm font-medium text-xelora-text shadow-sm transition-colors hover:bg-xelora-surface-2',
            collapsed ? 'justify-center' : 'px-3'
          )}
        >
          <SquarePen className="h-4 w-4 shrink-0" />
          {!collapsed && 'New chat'}
        </Link>
      </div>

      <nav className="mt-3 px-2.5" aria-label="Sections">
        <ul className="space-y-0.5">
          {navItems.map(({ href, label, icon: Icon }) => {
            const active = isActive(href);
            return (
              <li key={href}>
                <Link
                  href={href}
                  onClick={close}
                  title={collapsed ? label : undefined}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    'flex h-9 items-center gap-2.5 rounded-lg text-sm transition-colors',
                    collapsed ? 'justify-center' : 'px-3',
                    active ? 'bg-xelora-surface-2 font-medium text-xelora-text' : 'text-xelora-text-secondary hover:bg-xelora-surface-2 hover:text-xelora-text'
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" strokeWidth={1.75} />
                  {!collapsed && label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="mt-5 min-h-0 flex-1 overflow-y-auto px-2.5">
        {!collapsed && (
          <section aria-label="Recent conversations">
            <p className="px-3 pb-1.5 text-xs font-medium text-xelora-text-muted">Recents</p>
            {chats === null ? (
              <div className="flex justify-center py-4 text-xelora-text-muted"><Loader2 className="h-4 w-4 animate-spin" /></div>
            ) : chats.length === 0 ? (
              <p className="px-3 py-1 text-xs text-xelora-text-muted">Your conversations will appear here.</p>
            ) : (
              <ul className="space-y-0.5 pb-3">
                {chats.map((chat) => {
                  const active = activeChat === String(chat.id);
                  return (
                    <li key={chat.id} className="group relative">
                      <Link
                        href={`/dashboard/agent?chat=${chat.id}`}
                        onClick={close}
                        title={chat.title}
                        className={cn(
                          'flex h-8 items-center gap-2 rounded-lg px-3 pr-8 text-[13px] transition-colors',
                          active ? 'bg-xelora-surface-2 text-xelora-text' : 'text-xelora-text-secondary hover:bg-xelora-surface-2 hover:text-xelora-text'
                        )}
                      >
                        <span className="min-w-0 flex-1 truncate">{chat.title}</span>
                        {!chat.is_read && !active && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-xelora-green" aria-label="Unread" />}
                      </Link>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button
                            className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-md text-xelora-text-muted opacity-0 transition-opacity hover:bg-xelora-border hover:text-xelora-text focus:opacity-100 group-hover:opacity-100"
                            aria-label={`Options for ${chat.title}`}
                          >
                            <MoreHorizontal className="h-4 w-4" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-36">
                          <DropdownMenuItem destructive onSelect={() => void removeChat(chat)}>
                            <Trash2 className="h-4 w-4" /> Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        )}
      </div>

      {!collapsed && usage && usageLimit !== null && (
        <Link href="/dashboard/usage" onClick={close} className="mx-2.5 mb-2 block rounded-lg px-3 py-2.5 transition-colors hover:bg-xelora-surface-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-xelora-text-secondary">AI actions</span>
            <span className="tabular-nums text-xelora-text-muted">{usage.aiActionsUsed.toLocaleString()} / {usageLimit.toLocaleString()}</span>
          </div>
          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-xelora-border" role="progressbar" aria-valuenow={usagePct} aria-valuemin={0} aria-valuemax={100}>
            <div className={cn('h-full rounded-full', usagePct >= 90 ? 'bg-xelora-error' : 'bg-xelora-green')} style={{ width: `${usagePct}%` }} />
          </div>
        </Link>
      )}

      <div className="border-t border-xelora-border p-2.5">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className={cn('flex w-full items-center gap-2.5 rounded-lg p-1.5 text-left transition-colors hover:bg-xelora-surface-2', collapsed && 'justify-center')}
              aria-label="Account menu"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-xelora-text text-xs font-semibold text-xelora-surface">
                {getInitials(user?.name ?? 'U')}
              </span>
              {!collapsed && (
                <>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-xelora-text">{user?.name ?? 'Account'}</span>
                    <span className="block truncate text-xs text-xelora-text-muted">{PLAN_LABEL[plan] ?? plan}</span>
                  </span>
                  <ChevronsUpDown className="h-4 w-4 shrink-0 text-xelora-text-muted" />
                </>
              )}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" side="top" className="w-60">
            <DropdownMenuLabel className="font-normal">
              <span className="block truncate text-sm font-medium text-xelora-text">{user?.name}</span>
              <span className="block truncate text-xs text-xelora-text-muted">{user?.email}</span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild><Link href="/dashboard/settings" onClick={close}><Settings className="h-4 w-4" /> Settings</Link></DropdownMenuItem>
            <DropdownMenuItem asChild><Link href="/dashboard/billing" onClick={close}><CreditCard className="h-4 w-4" /> Plan and billing</Link></DropdownMenuItem>
            <DropdownMenuItem asChild><Link href="/dashboard/usage" onClick={close}><Activity className="h-4 w-4" /> Usage</Link></DropdownMenuItem>
            <DropdownMenuItem asChild><Link href="/dashboard/notifications" onClick={close}><Bell className="h-4 w-4" /> Notifications</Link></DropdownMenuItem>
            <DropdownMenuItem asChild><Link href="/dashboard/team" onClick={close}><Users className="h-4 w-4" /> Team</Link></DropdownMenuItem>
            <DropdownMenuItem asChild><Link href="/dashboard/devices" onClick={close}><MonitorSmartphone className="h-4 w-4" /> Devices</Link></DropdownMenuItem>
            {!desktop && (
              <DropdownMenuItem asChild><Link href="/download" onClick={close}><Download className="h-4 w-4" /> Get Xelora Desktop</Link></DropdownMenuItem>
            )}
            <DropdownMenuItem asChild><Link href="/dashboard/help" onClick={close}><CircleHelp className="h-4 w-4" /> Help</Link></DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem destructive onSelect={() => void handleLogout()}><LogOut className="h-4 w-4" /> Sign out</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </aside>
  );
}
