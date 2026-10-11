'use client';
import { useState, useEffect, useRef } from 'react';
import { Search, FolderOpen, FilePlus2, Sparkles, ListChecks, Settings, BarChart2, History, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DesktopView } from './types';

interface Command { id: string; label: string; description: string; icon: React.FC<{ className?: string }>; action: () => void; }

interface Props {
  onClose: () => void;
  onViewChange: (v: DesktopView) => void;
  onNewTask: () => void;
}

export function DesktopCommandPalette({ onClose, onViewChange, onNewTask }: Props) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: Command[] = [
    { id: 'open', label: 'Open workbook', description: 'Browse and open a local or cloud spreadsheet', icon: FolderOpen, action: () => { onViewChange('workbooks'); onClose(); } },
    { id: 'new-workbook', label: 'Create workbook', description: 'Start a new blank spreadsheet', icon: FilePlus2, action: () => { onClose(); } },
    { id: 'new-task', label: 'New Xelora task', description: 'Describe spreadsheet work for Xelora to plan', icon: Sparkles, action: () => { onNewTask(); } },
    { id: 'workflows', label: 'Open workflows', description: 'Browse and run saved workflows', icon: ListChecks, action: () => { onViewChange('workflows'); onClose(); } },
    { id: 'reports', label: 'Open reports', description: 'View generated reports and charts', icon: BarChart2, action: () => { onViewChange('reports'); onClose(); } },
    { id: 'history', label: 'Task history', description: 'Review past Xelora tasks and results', icon: History, action: () => { onViewChange('history'); onClose(); } },
    { id: 'settings', label: 'Open settings', description: 'Configure Xelora Desktop preferences', icon: Settings, action: () => { onViewChange('settings'); onClose(); } },
  ];

  const filtered = commands.filter(c =>
    !query || c.label.toLowerCase().includes(query.toLowerCase()) || c.description.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => { inputRef.current?.focus(); }, []);
  useEffect(() => { setSelectedIndex(0); }, [query]);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { onClose(); return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIndex(i => Math.min(i + 1, filtered.length - 1)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); setSelectedIndex(i => Math.max(i - 1, 0)); }
    if (e.key === 'Enter' && filtered[selectedIndex]) { filtered[selectedIndex].action(); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4" role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="absolute inset-0 bg-xelora-black/40" onClick={onClose} />
      <div className="relative w-full max-w-lg rounded-xl border border-xelora-border bg-white shadow-xl overflow-hidden">
        <div className="flex items-center gap-3 border-b border-xelora-border px-4 py-3">
          <Search className="h-4 w-4 text-xelora-text-muted shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Search commands…"
            className="flex-1 text-sm text-xelora-text placeholder:text-xelora-text-muted focus:outline-none"
            aria-label="Search commands"
          />
          <button onClick={onClose} className="h-6 w-6 flex items-center justify-center rounded text-xelora-text-muted hover:bg-xelora-surface-2 transition-colors" aria-label="Close command palette">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        <ul className="py-1 max-h-80 overflow-y-auto" role="listbox">
          {filtered.length === 0 && (
            <li className="px-4 py-6 text-center text-sm text-xelora-text-muted">No commands found for &quot;{query}&quot;</li>
          )}
          {filtered.map((cmd, i) => {
            const Icon = cmd.icon;
            return (
              <li key={cmd.id} role="option" aria-selected={selectedIndex === i}>
                <button
                  onClick={cmd.action}
                  onMouseEnter={() => setSelectedIndex(i)}
                  className={cn(
                    'flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors',
                    selectedIndex === i ? 'bg-xelora-surface-2' : 'hover:bg-xelora-surface-2'
                  )}
                >
                  <div className={cn('flex h-7 w-7 items-center justify-center rounded border shrink-0', selectedIndex === i ? 'border-xelora-green bg-xelora-success-bg' : 'border-xelora-border bg-white')}>
                    <Icon className={cn('h-3.5 w-3.5', selectedIndex === i ? 'text-xelora-green' : 'text-xelora-text-secondary')} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-xelora-text">{cmd.label}</p>
                    <p className="text-xs text-xelora-text-muted truncate">{cmd.description}</p>
                  </div>
                  {selectedIndex === i && <kbd className="text-[10px] text-xelora-text-muted bg-xelora-border rounded px-1.5 py-0.5">↵</kbd>}
                </button>
              </li>
            );
          })}
        </ul>

        <div className="border-t border-xelora-border px-4 py-2 flex gap-4 text-[10px] text-xelora-text-muted">
          <span><kbd className="bg-xelora-border rounded px-1">↑↓</kbd> navigate</span>
          <span><kbd className="bg-xelora-border rounded px-1">↵</kbd> select</span>
          <span><kbd className="bg-xelora-border rounded px-1">Esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}
