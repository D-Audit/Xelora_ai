'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth-store';
import { useUIStore } from '@/stores/ui-store';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import { Menu, Bell, Search, HelpCircle, ChevronDown, LogOut, Settings, CreditCard, User, Globe, MonitorSpeaker, Activity, History } from 'lucide-react';
import { getInitials } from '@/lib/utils';
import { mockNotifications } from '@/data/mock-notifications';

export function Topbar() {
  const { user, logout } = useAuthStore();
  const { toggleSidebar } = useUIStore();
  const router = useRouter();
  const unreadCount = mockNotifications.filter(n => !n.isRead).length;

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  const planLabel = user?.plan === 'professional' ? 'Professional' :
    user?.plan === 'starter' ? 'Starter' :
    user?.plan === 'business' ? 'Business' : 'Trial';

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-xelora-border bg-white px-4 sm:px-6">
      {/* Mobile menu toggle */}
      <button
        onClick={toggleSidebar}
        className="lg:hidden flex h-8 w-8 items-center justify-center rounded text-xelora-text-secondary hover:bg-xelora-surface-2 transition-colors"
        aria-label="Open navigation"
      >
        <Menu className="h-4 w-4" />
      </button>

      {/* Search */}
      <div className="flex-1 max-w-xs hidden sm:flex">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-xelora-text-muted" aria-hidden="true" />
          <input
            type="search"
            placeholder="Search workflows, files…"
            className="h-8 w-full rounded-md border border-xelora-border bg-xelora-surface-2 pl-9 pr-3 text-sm text-xelora-text placeholder:text-xelora-text-muted focus:outline-none focus:ring-2 focus:ring-xelora-border-focus"
            aria-label="Search"
          />
        </div>
      </div>

      <div className="ml-auto flex items-center gap-2">
        {/* Plan badge */}
        <Badge variant="success" className="hidden sm:flex text-xs">
          {planLabel}
        </Badge>

        {/* Notifications */}
        <Button variant="ghost" size="icon" className="relative" asChild>
          <Link href="/dashboard/notifications" aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}>
            <Bell className="h-4 w-4 text-xelora-text-secondary" />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-xelora-error" aria-hidden="true" />
            )}
          </Link>
        </Button>

        {/* User menu - everything account/utility-related lives here
            instead of cluttering the main sidebar with every settings
            sub-page. */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2 rounded-md px-2 py-1 text-sm hover:bg-xelora-surface-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-xelora-border-focus">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-xelora-green text-white text-xs font-semibold" aria-hidden="true">
                {getInitials(user?.name ?? 'U')}
              </span>
              <span className="hidden sm:block text-xelora-text font-medium max-w-[120px] truncate">
                {user?.name}
              </span>
              <ChevronDown className="h-3.5 w-3.5 text-xelora-text-muted" aria-hidden="true" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="flex flex-col gap-0.5 py-2">
              <span className="font-medium text-xelora-text">{user?.name}</span>
              <span className="text-xs text-xelora-text-muted font-normal">{user?.email}</span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/dashboard/settings" className="flex items-center gap-2">
                <User className="h-4 w-4" />
                Profile
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/dashboard/settings" className="flex items-center gap-2">
                <Settings className="h-4 w-4" />
                Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/dashboard/settings" className="flex items-center gap-2">
                <Globe className="h-4 w-4" />
                Language
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/dashboard/billing" className="flex items-center gap-2">
                <CreditCard className="h-4 w-4" />
                Upgrade plan
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/dashboard/usage" className="flex items-center gap-2">
                <Activity className="h-4 w-4" />
                Usage
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/dashboard/devices" className="flex items-center gap-2">
                <MonitorSpeaker className="h-4 w-4" />
                Devices
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/dashboard/history" className="flex items-center gap-2">
                <History className="h-4 w-4" />
                History
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/dashboard/help" className="flex items-center gap-2">
                <HelpCircle className="h-4 w-4" />
                Help
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} destructive className="flex items-center gap-2">
              <LogOut className="h-4 w-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
