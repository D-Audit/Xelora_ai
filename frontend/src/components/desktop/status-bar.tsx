import { Wifi, Zap } from 'lucide-react';
import type { DesktopTask } from './types';

interface Props { tasks: DesktopTask[]; }

export function DesktopStatusBar({ tasks }: Props) {
  const running = tasks.filter(t => t.status === 'running').length;
  const approval = tasks.filter(t => t.status === 'awaiting_approval').length;

  return (
    <div className="flex h-7 items-center justify-between border-t border-xelora-border bg-xelora-surface-2 px-4 text-[11px] text-xelora-text-muted shrink-0">
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1"><Wifi className="h-3 w-3" />Connected</span>
        {running > 0 && <span className="flex items-center gap-1 text-xelora-info"><span className="h-1.5 w-1.5 rounded-full bg-xelora-info animate-pulse" />{running} running</span>}
        {approval > 0 && <span className="flex items-center gap-1 text-amber-500"><span className="h-1.5 w-1.5 rounded-full bg-amber-400" />{approval} awaiting approval</span>}
      </div>
      <span className="flex items-center gap-1"><Zap className="h-3 w-3 text-xelora-green" />Xelora Desktop — frontend simulation</span>
    </div>
  );
}
