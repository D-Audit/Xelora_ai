'use client';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { useUIStore } from '@/stores/ui-store';
import { useAuthStore } from '@/stores/auth-store';
import { XeloraLogo } from '@/components/ui/xelora-logo';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import {
  LayoutDashboard, GitBranch, Files, LayoutTemplate, Settings,
  Users, ChevronLeft, X, Bot, Plus, History, Loader2, MessageSquare,
  MoreHorizontal, Check, Trash2, ChevronDown, LogOut, User, CreditCard,
  Activity, MonitorSpeaker, HelpCircle, Globe
} from 'lucide-react';
import { mockUsage } from '@/data/mock-usage';
import { formatRelativeTime, getInitials, getUsagePercentage } from '@/lib/utils';
import { isDesktopApp } from '@/lib/is-desktop';
import { deleteChat, listChats, markChatRead } from '@/services/agent';
import type { ChatSummary } from '@/services/agent';
import { useEffect, useState } from 'react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

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
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toggleSidebarCollapsed, setSidebarOpen } = useUIStore();
  const { user, logout } = useAuthStore();
  const aiPct = getUsagePercentage(mockUsage.aiActionsUsed, mockUsage.aiActionsLimit);

  // Starts false to match server-rendered HTML (avoids a hydration
  // mismatch), then flips true on mount if we're inside the desktop
  // app - see src/lib/is-desktop.ts.
  const [showDesktopItems, setShowDesktopItems] = useState(false);
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [loadingChats, setLoadingChats] = useState(false);
  const isChatWorkspace = pathname === '/dashboard/agent';
  useEffect(() => setShowDesktopItems(isDesktopApp()), []);

  useEffect(() => {
    if (!isChatWorkspace || collapsed) return;

    const loadChats = () => {
      setLoadingChats(true);
      listChats()
        .then(setChats)
        .catch(() => setChats([]))
        .finally(() => setLoadingChats(false));
    };

    loadChats();
    window.addEventListener('xelora:chats-updated', loadChats);
    return () => window.removeEventListener('xelora:chats-updated', loadChats);
  }, [collapsed, isChatWorkspace]);

  const isActive = (href: string, exact = false) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + '/');

  const handleConversationAction = async (chat: ChatSummary, action: 'mark-read' | 'delete') => {
    try {
      if (action === 'mark-read') {
        await markChatRead(chat.id);
      } else {
        await deleteChat(chat.id);
        if (searchParams.get('chat') === String(chat.id)) router.replace('/dashboard/agent?new=1');
      }
      window.dispatchEvent(new Event('xelora:chats-updated'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not update this conversation.');
    }
  };

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  return (
    <aside
      className={cn(
        'flex h-full flex-col border-r border-xelora-border bg-xelora-surface-2 text-xelora-text transition-all duration-200',
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
          <Link href="/dashboard/agent?new=1" className="mb-4 flex items-center justify-center gap-2 rounded-lg bg-xelora-deep-green px-3 py-2.5 text-sm font-medium text-white transition-colors hover:bg-xelora-green">
            <Plus className="h-4 w-4" /> New task
          </Link>
        )}
        {collapsed && <Link href="/dashboard/agent?new=1" aria-label="New task" className="mb-4 flex h-10 items-center justify-center rounded-lg bg-xelora-deep-green text-white"><Plus className="h-4 w-4" /></Link>}
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
        {isChatWorkspace && !collapsed && (
          <section className="mt-6 border-t border-xelora-border pt-5" aria-label="Recent conversations">
            <div className="mb-2 flex items-center justify-between px-3">
              <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-xelora-text-muted">Recents</p>
              <span className="text-[10px] text-xelora-text-muted">{chats.length}</span>
            </div>
            {loadingChats ? (
              <div className="flex justify-center py-4 text-xelora-text-muted"><Loader2 className="h-4 w-4 animate-spin" /></div>
            ) : chats.length === 0 ? (
              <p className="px-3 py-2 text-xs text-xelora-text-muted">No conversations yet.</p>
            ) : (
              <ul role="list" className="space-y-1">
                {chats.map((chat) => {
                  const active = searchParams.get('chat') === String(chat.id);
                  return (
                    <li key={chat.id} className="group relative">
                      <Link
                        href={`/dashboard/agent?chat=${chat.id}`}
                        onClick={() => setSidebarOpen(false)}
                        className={cn(
                          'flex min-w-0 items-start gap-2 rounded-lg px-3 py-2.5 pr-9 transition-colors',
                          active ? 'bg-white text-xelora-text shadow-sm ring-1 ring-black/[0.03]' : 'text-xelora-text-secondary hover:bg-white/80 hover:text-xelora-text'
                        )}
                      >
                        <div className={cn('mt-1 h-1.5 w-1.5 shrink-0 rounded-full', chat.is_read ? 'bg-transparent' : 'bg-xelora-green')} />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-xs font-medium">{chat.title}</p>
                          <p className="mt-0.5 flex items-center gap-1 text-[10px] text-xelora-text-muted">
                            <MessageSquare className="h-3 w-3" />
                            {chat.created_at ? formatRelativeTime(chat.created_at) : 'Recent'}
                          </p>
                        </div>
                      </Link>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button
                            className="absolute right-1.5 top-2.5 flex h-6 w-6 items-center justify-center rounded-md text-xelora-text-muted opacity-0 transition-opacity hover:bg-xelora-surface-2 hover:text-xelora-text focus:opacity-100 group-hover:opacity-100"
                            aria-label={`Conversation options for ${chat.title}`}
                          >
                            <MoreHorizontal className="h-4 w-4" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-40">
                          {!chat.is_read && (
                            <DropdownMenuItem onSelect={() => void handleConversationAction(chat, 'mark-read')}>
                              <Check className="h-4 w-4" /> Mark as read
                            </DropdownMenuItem>
                          )}
                          {!chat.is_read && <DropdownMenuSeparator />}
                          <DropdownMenuItem destructive onSelect={() => void handleConversationAction(chat, 'delete')}>
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
      <div className="border-t border-xelora-border p-2">
        <Link href="/dashboard/settings" className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-xelora-text-secondary hover:bg-black/[0.045] hover:text-xelora-text"><Settings className="h-4 w-4" />{!collapsed && 'Settings'}</Link>
        <Link href="/dashboard/history" className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-xelora-text-secondary hover:bg-black/[0.045] hover:text-xelora-text"><History className="h-4 w-4" />{!collapsed && 'Task history'}</Link>
      </div>
      <div className="border-t border-xelora-border p-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className={cn('flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-xelora-border-focus', collapsed && 'justify-center')}
              aria-label="Open account menu"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-xelora-deep-green text-xs font-semibold text-white">
                {getInitials(user?.name ?? 'U')}
              </span>
              {!collapsed && (
                <>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-xelora-text">{user?.name ?? 'Account'}</span>
                    <span className="block truncate text-xs text-xelora-text-muted">{user?.email}</span>
                  </span>
                  <ChevronDown className="h-4 w-4 shrink-0 text-xelora-text-muted" />
                </>
              )}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" side="top" className="w-56">
            <DropdownMenuLabel className="flex flex-col gap-0.5 py-2">
              <span className="font-medium text-xelora-text">{user?.name}</span>
              <span className="text-xs font-normal text-xelora-text-muted">{user?.email}</span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild><Link href="/dashboard/settings"><User className="h-4 w-4" /> Profile</Link></DropdownMenuItem>
            <DropdownMenuItem asChild><Link href="/dashboard/settings"><Globe className="h-4 w-4" /> Language</Link></DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild><Link href="/dashboard/billing"><CreditCard className="h-4 w-4" /> Upgrade plan</Link></DropdownMenuItem>
            <DropdownMenuItem asChild><Link href="/dashboard/usage"><Activity className="h-4 w-4" /> Usage</Link></DropdownMenuItem>
            <DropdownMenuItem asChild><Link href="/dashboard/devices"><MonitorSpeaker className="h-4 w-4" /> Devices</Link></DropdownMenuItem>
            <DropdownMenuItem asChild><Link href="/dashboard/help"><HelpCircle className="h-4 w-4" /> Help</Link></DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem destructive onSelect={() => void handleLogout()}><LogOut className="h-4 w-4" /> Sign out</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </aside>
  );
}
