'use client';
import { useState, useRef, useEffect } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { DesktopIconRail } from '@/components/desktop/icon-rail';
import { DesktopContextSidebar } from '@/components/desktop/context-sidebar';
import { DesktopWorkspace } from '@/components/desktop/workspace';
import { DesktopStatusBar } from '@/components/desktop/status-bar';
import { DesktopCommandPalette } from '@/components/desktop/command-palette';
import type { DesktopView, DesktopTask } from '@/components/desktop/types';
import { mockDesktopTasks } from '@/data/mock-desktop';
import { cn } from '@/lib/utils';

export default function XeloraDesktopPage() {
  const user = useAuthStore(s => s.user);
  const [activeView, setActiveView] = useState<DesktopView>('home');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeTask, setActiveTask] = useState<DesktopTask | null>(null);
  const [tasks, setTasks] = useState<DesktopTask[]>(mockDesktopTasks);
  const [commandOpen, setCommandOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setCommandOpen(v => !v);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[#F7F9F8] select-none">
      <div className="flex h-9 items-center justify-between bg-xelora-nav px-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <span className="h-3 w-3 rounded-full bg-[#FF5F57] cursor-pointer" />
            <span className="h-3 w-3 rounded-full bg-[#FEBC2E] cursor-pointer" />
            <span className="h-3 w-3 rounded-full bg-[#28C840] cursor-pointer" />
          </div>
          <span className="text-xs font-medium text-white/60">Xelora Desktop</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCommandOpen(true)}
            className="flex items-center gap-2 rounded border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/50 hover:bg-white/10 transition-colors"
          >
            <span>Search or run command</span>
            <kbd className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-mono">Ctrl K</kbd>
          </button>
        </div>
        <span className="text-xs text-white/40">{user?.name}</span>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <DesktopIconRail
          activeView={activeView}
          onViewChange={setActiveView}
          user={user}
        />
        <div className={cn('flex h-full transition-all duration-200', sidebarOpen ? 'w-64' : 'w-0', 'overflow-hidden shrink-0')}>
          <DesktopContextSidebar
            view={activeView}
            tasks={tasks}
            activeTask={activeTask}
            onSelectTask={t => { setActiveTask(t); setActiveView('tasks'); }}
            onNewTask={() => { setActiveTask(null); setActiveView('home'); }}
          />
        </div>
        <DesktopWorkspace
          view={activeView}
          activeTask={activeTask}
          tasks={tasks}
          setTasks={setTasks}
          setActiveTask={setActiveTask}
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(v => !v)}
          onViewChange={setActiveView}
          user={user}
        />
      </div>

      <DesktopStatusBar tasks={tasks} />

      {commandOpen && (
        <DesktopCommandPalette
          onClose={() => setCommandOpen(false)}
          onViewChange={v => { setActiveView(v); setCommandOpen(false); }}
          onNewTask={() => { setActiveTask(null); setActiveView('home'); setCommandOpen(false); }}
        />
      )}
    </div>
  );
}
