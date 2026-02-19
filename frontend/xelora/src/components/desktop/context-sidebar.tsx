'use client';
import { Plus, Loader2, CheckCircle2, AlertTriangle, XCircle, PauseCircle, MoreHorizontal, Pin, FolderOpen, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '@/lib/utils';
import type { DesktopView, DesktopTask } from './types';
import { mockDesktopWorkbooks } from '@/data/mock-desktop';

interface Props {
  view: DesktopView;
  tasks: DesktopTask[];
  activeTask: DesktopTask | null;
  onSelectTask: (t: DesktopTask) => void;
  onNewTask: () => void;
}

const statusIcon: Record<string, React.FC<{ className?: string }>> = {
  running: Loader2,
  awaiting_approval: AlertTriangle,
  completed: CheckCircle2,
  completed_with_warnings: AlertTriangle,
  failed: XCircle,
  paused: PauseCircle,
  draft: Clock,
  cancelled: XCircle,
};

const statusColour: Record<string, string> = {
  running: 'text-xelora-info',
  awaiting_approval: 'text-amber-400',
  completed: 'text-xelora-green',
  completed_with_warnings: 'text-amber-400',
  failed: 'text-xelora-error',
  paused: 'text-xelora-text-muted',
  draft: 'text-xelora-text-muted',
  cancelled: 'text-xelora-text-muted',
};

export function DesktopContextSidebar({ view, tasks, activeTask, onSelectTask, onNewTask }: Props) {
  const running = tasks.filter(t => t.status === 'running');
  const approval = tasks.filter(t => t.status === 'awaiting_approval');
  const recent = tasks.filter(t => !['running', 'awaiting_approval'].includes(t.status));

  return (
    <aside className="flex h-full w-full flex-col bg-white border-r border-xelora-border overflow-hidden">
      {/* New Task button */}
      <div className="px-3 pt-3 pb-2 shrink-0">
        <button
          onClick={onNewTask}
          className="flex w-full items-center gap-2 rounded-md bg-xelora-green px-3 py-2 text-sm font-medium text-white hover:bg-xelora-deep-green transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-xelora-border-focus"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          New Task
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {(view === 'home' || view === 'tasks') && (
          <>
            {running.length > 0 && (
              <SidebarSection label="Running">
                {running.map(t => <TaskItem key={t.id} task={t} active={activeTask?.id === t.id} onSelect={onSelectTask} />)}
              </SidebarSection>
            )}
            {approval.length > 0 && (
              <SidebarSection label="Needs approval">
                {approval.map(t => <TaskItem key={t.id} task={t} active={activeTask?.id === t.id} onSelect={onSelectTask} />)}
              </SidebarSection>
            )}
            {recent.length > 0 && (
              <SidebarSection label="Recent">
                {recent.map(t => <TaskItem key={t.id} task={t} active={activeTask?.id === t.id} onSelect={onSelectTask} />)}
              </SidebarSection>
            )}
            {tasks.length === 0 && (
              <div className="px-2 py-6 text-center">
                <p className="text-xs font-medium text-xelora-text">No spreadsheet tasks yet</p>
                <p className="text-xs text-xelora-text-muted mt-1">Open a workbook or ask Xelora to start.</p>
              </div>
            )}
          </>
        )}

        {view === 'workbooks' && (
          <>
            <SidebarSection label="Recent workbooks">
              {mockDesktopWorkbooks.map(wb => (
                <button key={wb.id} className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left hover:bg-xelora-surface-2 transition-colors">
                  <FolderOpen className="h-3.5 w-3.5 text-xelora-green shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-xelora-text truncate">{wb.name}</p>
                    <p className="text-[10px] text-xelora-text-muted capitalize">{wb.source} · {formatRelativeTime(wb.lastOpened)}</p>
                  </div>
                </button>
              ))}
            </SidebarSection>
          </>
        )}

        {view === 'settings' && (
          <>
            {['General', 'Files', 'AI preferences', 'Privacy', 'Notifications', 'Appearance', 'Account', 'About Xelora'].map(item => (
              <button key={item} className="flex w-full items-center rounded-md px-3 py-2 text-left text-sm text-xelora-text-secondary hover:bg-xelora-surface-2 transition-colors">
                {item}
              </button>
            ))}
          </>
        )}

        {view === 'history' && (
          <>
            {['Today', 'Yesterday', 'Previous 7 days', 'Previous 30 days'].map(period => (
              <SidebarSection key={period} label={period}>
                {tasks.filter(() => true).slice(0, 1).map(t => (
                  <TaskItem key={t.id} task={t} active={activeTask?.id === t.id} onSelect={onSelectTask} />
                ))}
              </SidebarSection>
            ))}
          </>
        )}
      </div>
    </aside>
  );
}

function SidebarSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <p className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-xelora-text-muted">{label}</p>
      {children}
    </div>
  );
}

function TaskItem({ task, active, onSelect }: { task: DesktopTask; active: boolean; onSelect: (t: DesktopTask) => void }) {
  const Icon = statusIcon[task.status] ?? Clock;
  const colour = statusColour[task.status] ?? 'text-xelora-text-muted';
  const isRunning = task.status === 'running';

  return (
    <button
      onClick={() => onSelect(task)}
      className={cn(
        'group flex w-full items-start gap-2 rounded-md px-2 py-2 text-left transition-colors',
        active ? 'bg-xelora-success-bg' : 'hover:bg-xelora-surface-2'
      )}
    >
      <Icon className={cn('h-3.5 w-3.5 mt-0.5 shrink-0', colour, isRunning && 'animate-spin')} aria-hidden="true" />
      <div className="flex-1 min-w-0">
        <p className={cn('text-xs font-medium truncate', active ? 'text-xelora-green' : 'text-xelora-text')}>{task.title}</p>
        <p className="text-[10px] text-xelora-text-muted truncate capitalize mt-0.5">
          {task.status.replace('_', ' ')} · {formatRelativeTime(task.updatedAt)}
        </p>
      </div>
      <button
        onClick={e => e.stopPropagation()}
        className="opacity-0 group-hover:opacity-100 h-5 w-5 flex items-center justify-center rounded hover:bg-xelora-border transition-all"
        aria-label="Task options"
      >
        <MoreHorizontal className="h-3 w-3 text-xelora-text-muted" />
      </button>
    </button>
  );
}
