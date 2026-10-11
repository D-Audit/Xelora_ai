import type { ReactNode } from 'react';

interface MockWindowProps {
  title?: string;
  subtitle?: string;
  children: ReactNode;
}

export function MockWindow({ title, subtitle, children }: MockWindowProps) {
  return (
    <div className="overflow-hidden rounded-xl border border-xelora-border bg-white shadow-sm">
      <div className="flex items-center gap-2 border-b border-xelora-border bg-xelora-surface-2 px-4 py-3">
        <div className="flex gap-1.5" aria-hidden="true">
          <span className="h-3 w-3 rounded-full bg-[#E2554F]" />
          <span className="h-3 w-3 rounded-full bg-[#F2C94C]" />
          <span className="h-3 w-3 rounded-full bg-[#27AE60]" />
        </div>
        <div className="min-w-0 flex-1">
          {title ? <p className="truncate text-sm font-medium text-xelora-text">{title}</p> : null}
          {subtitle ? <p className="truncate text-xs text-xelora-text-muted">{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </div>
  );
}
