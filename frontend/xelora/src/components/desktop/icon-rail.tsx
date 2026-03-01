'use client';
import { Home, FolderOpen, Sparkles, ListChecks, BarChart2, History, LayoutTemplate, Bell, Settings, UserCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DesktopView } from './types';
import type { User } from '@/types';
import { getInitials } from '@/lib/utils';

interface RailItem {
  id: DesktopView;
  icon: React.FC<{ className?: string }>;
  label: string;
}

const topItems: RailItem[] = [
  { id: 'home', icon: Home, label: 'Home' },
  { id: 'workbooks', icon: FolderOpen, label: 'Workbooks' },
  { id: 'tasks', icon: Sparkles, label: 'Xelora Tasks' },
  { id: 'workflows', icon: ListChecks, label: 'Workflows' },
  { id: 'reports', icon: BarChart2, label: 'Reports' },
  { id: 'history', icon: History, label: 'History' },
  { id: 'templates', icon: LayoutTemplate, label: 'Templates' },
];

const bottomItems: RailItem[] = [
  { id: 'notifications', icon: Bell, label: 'Notifications' },
  { id: 'settings', icon: Settings, label: 'Settings' },
];

interface Props {
  activeView: DesktopView;
  onViewChange: (v: DesktopView) => void;
  user: User | null;
}

export function DesktopIconRail({ activeView, onViewChange, user }: Props) {
  return (
    <nav
      className="flex w-14 flex-col items-center bg-xelora-nav border-r border-white/10 py-3 shrink-0"
      aria-label="Primary navigation"
    >
      <div className="flex flex-col items-center gap-0.5 flex-1">
        {topItems.map(({ id, icon: Icon, label }) => (
          <RailButton key={id} id={id} icon={Icon} label={label} active={activeView === id} onClick={() => onViewChange(id)} />
        ))}
      </div>
      <div className="flex flex-col items-center gap-0.5 mt-auto">
        {bottomItems.map(({ id, icon: Icon, label }) => (
          <RailButton key={id} id={id} icon={Icon} label={label} active={activeView === id} onClick={() => onViewChange(id)} />
        ))}
        {/* User avatar */}
        <button
          className="mt-2 flex h-8 w-8 items-center justify-center rounded-full bg-xelora-green text-white text-xs font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-xelora-bright-green"
          aria-label={`User: ${user?.name ?? 'Account'}`}
          title={user?.name ?? 'Account'}
        >
          {getInitials(user?.name ?? 'U')}
        </button>
      </div>
    </nav>
  );
}

function RailButton({ id, icon: Icon, label, active, onClick }: { id: string; icon: React.FC<{className?: string}>; label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'relative flex h-10 w-10 items-center justify-center rounded-md transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-xelora-bright-green',
        active
          ? 'bg-xelora-bright-green/10 text-xelora-bright-green'
          : 'text-white/50 hover:bg-white/8 hover:text-white/80'
      )}
    >
      {active && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-r-full bg-xelora-bright-green" aria-hidden="true" />
      )}
      <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
    </button>
  );
}
