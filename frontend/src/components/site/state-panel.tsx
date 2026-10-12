import { AlertCircle, Loader2, Lock, Search, ShieldAlert } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

interface StatePanelProps {
  kind: 'loading' | 'empty' | 'error' | 'permission' | 'plan';
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

const iconMap = {
  loading: Loader2,
  empty: Search,
  error: AlertCircle,
  permission: Lock,
  plan: ShieldAlert,
} as const;

export function StatePanel({
  kind,
  title,
  description,
  actionLabel,
  onAction,
}: StatePanelProps) {
  const Icon = iconMap[kind];

  return (
    <Card className="p-6">
      <div className="flex flex-col items-center text-center">
        <Icon className={`h-6 w-6 ${kind === 'loading' ? 'animate-spin text-xelora-text-muted' : 'text-xelora-text-muted'}`} strokeWidth={1.5} />
        <h3 className="mt-4 text-base font-semibold text-xelora-text">{title}</h3>
        <p className="mt-2 max-w-md text-sm text-xelora-text-secondary">{description}</p>
        {actionLabel && onAction ? (
          <Button className="mt-5" variant="outline" onClick={onAction}>
            {actionLabel}
          </Button>
        ) : null}
      </div>
    </Card>
  );
}
