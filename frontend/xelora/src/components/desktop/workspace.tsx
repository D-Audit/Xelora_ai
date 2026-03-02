'use client';
import { useState } from 'react';
import { PanelLeftOpen, PanelLeftClose } from 'lucide-react';
import type { DesktopView, DesktopTask } from './types';
import type { User } from '@/types';
import { WelcomeWorkspace } from './workspace-welcome';
import { TaskThreadWorkspace } from './workspace-task-thread';
import { SpreadsheetWorkspace } from './workspace-spreadsheet';
import { SettingsWorkspace } from './workspace-settings';

interface Props {
  view: DesktopView;
  activeTask: DesktopTask | null;
  tasks: DesktopTask[];
  setTasks: React.Dispatch<React.SetStateAction<DesktopTask[]>>;
  setActiveTask: (t: DesktopTask | null) => void;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onViewChange: (v: DesktopView) => void;
  user: User | null;
}

export function DesktopWorkspace(props: Props) {
  const { view, activeTask, tasks, setTasks, setActiveTask, sidebarOpen, onToggleSidebar, onViewChange, user } = props;
  const [spreadsheetFile, setSpreadsheetFile] = useState<string | null>(null);

  const openSpreadsheet = (name: string) => { setSpreadsheetFile(name); };

  return (
    <div className="flex flex-1 flex-col bg-white overflow-hidden">
      {/* Top bar */}
      <div className="flex h-10 items-center gap-3 border-b border-xelora-border px-4 shrink-0">
        <button
          onClick={onToggleSidebar}
          className="flex h-7 w-7 items-center justify-center rounded text-xelora-text-secondary hover:bg-xelora-surface-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-xelora-border-focus"
          aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
        </button>
        <span className="text-sm font-medium text-xelora-text-secondary">
          {view === 'settings' ? 'Settings' : activeTask ? activeTask.workbook : 'Xelora Desktop'}
        </span>
        {activeTask && (
          <span className="ml-auto text-xs text-xelora-text-muted capitalize">
            {activeTask.status.replace('_', ' ')}
          </span>
        )}
      </div>

      {/* Workspace content */}
      <div className="flex-1 overflow-hidden">
        {view === 'settings' ? (
          <SettingsWorkspace />
        ) : spreadsheetFile ? (
          <SpreadsheetWorkspace fileName={spreadsheetFile} onClose={() => setSpreadsheetFile(null)} />
        ) : (view === 'home' || view === 'tasks') && activeTask ? (
          <TaskThreadWorkspace
            task={activeTask}
            tasks={tasks}
            setTasks={setTasks}
            setActiveTask={setActiveTask}
            onOpenSpreadsheet={openSpreadsheet}
          />
        ) : (
          <WelcomeWorkspace
            user={user}
            tasks={tasks}
            onSelectTask={t => { setActiveTask(t); onViewChange('tasks'); }}
            onOpenSpreadsheet={openSpreadsheet}
          />
        )}
      </div>
    </div>
  );
}
