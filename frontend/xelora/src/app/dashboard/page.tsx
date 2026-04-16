'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuthStore } from '@/stores/auth-store';
import { getDashboardSummary } from '@/services/dashboard';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { MonitorPlay, Upload, Plus, CheckCircle2, Clock, AlertTriangle, XCircle, FileSpreadsheet, ExternalLink, AlertCircle } from 'lucide-react';
import { formatDate, formatFileSize, formatRelativeTime, getUsagePercentage, getUsageBarColour } from '@/lib/utils';
import type { UsageLimits, Subscription, FileRecord, WorkflowRun, Notification } from '@/types';
import { toast } from 'sonner';

interface DashboardData {
  usage: UsageLimits;
  subscription: Subscription;
  recentFiles: FileRecord[];
  recentRuns: WorkflowRun[];
  alerts: Notification[];
}

const statusConfig = {
  completed: { label: 'Completed', icon: CheckCircle2, colour: 'text-xelora-success' },
  completed_with_warnings: { label: 'Warnings', icon: AlertTriangle, colour: 'text-xelora-warning' },
  failed: { label: 'Failed', icon: XCircle, colour: 'text-xelora-error' },
  running: { label: 'Running', icon: Clock, colour: 'text-xelora-info' },
  cancelled: { label: 'Cancelled', icon: XCircle, colour: 'text-xelora-text-muted' },
  paused: { label: 'Paused', icon: Clock, colour: 'text-xelora-warning' },
  awaiting_approval: { label: 'Awaiting approval', icon: AlertCircle, colour: 'text-xelora-info' },
};

const fileStatusBadge: Record<string, { label: string; variant: 'success' | 'info' | 'warning' | 'error' | 'default' }> = {
  ready: { label: 'Ready', variant: 'default' },
  processing: { label: 'Processing', variant: 'info' },
  completed: { label: 'Completed', variant: 'success' },
  needs_review: { label: 'Needs review', variant: 'warning' },
  failed: { label: 'Failed', variant: 'error' },
  archived: { label: 'Archived', variant: 'default' },
};

export default function DashboardPage() {
  const user = useAuthStore(s => s.user);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboardSummary().then(d => { setData(d); setLoading(false); });
  }, []);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const firstName = user?.name?.split(' ')[0] ?? 'there';

  const usageItems = data ? [
    { label: 'AI actions', used: data.usage.aiActionsUsed, limit: data.usage.aiActionsLimit as number, suffix: 'actions' },
    { label: 'Workflow runs', used: data.usage.workflowRunsUsed, limit: data.usage.workflowRunsLimit as number, suffix: 'runs' },
    { label: 'Storage', used: Math.round(data.usage.storageUsedGB * 10) / 10, limit: data.usage.storageLimitGB, suffix: 'GB' },
    { label: 'Devices', used: data.usage.devicesUsed, limit: data.usage.devicesLimit, suffix: 'devices' },
  ] : [];

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          {loading ? (
            <>
              <Skeleton className="h-7 w-48 mb-2" />
              <Skeleton className="h-4 w-72" />
            </>
          ) : (
            <>
              <h1 className="text-2xl font-semibold text-xelora-text">{greeting}, {firstName}</h1>
              <p className="text-sm text-xelora-text-secondary mt-0.5">
                Manage your Xelora account, workflows, files, and desktop access.
              </p>
            </>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href="/desktop"><MonitorPlay className="h-4 w-4" />Open Xelora Desktop</Link>
          </Button>
          <Button variant="outline" size="sm" onClick={() => toast.info('Upload files from the Files page.')}>
            <Upload className="h-4 w-4" />Upload Spreadsheet
          </Button>
          <Button size="sm" asChild>
            <Link href="/dashboard/workflows/new"><Plus className="h-4 w-4" />Create Workflow</Link>
          </Button>
        </div>
      </div>

      {/* Alerts */}
      {!loading && data?.alerts && data.alerts.length > 0 && (
        <div className="space-y-2">
          {data.alerts.map(alert => (
            <Alert key={alert.id} variant="warning">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>{alert.title}</AlertTitle>
              <AlertDescription className="flex items-center justify-between gap-2 flex-wrap">
                <span>{alert.message}</span>
                {alert.actionUrl && (
                  <Link href={alert.actionUrl} className="text-xs font-medium text-xelora-warning hover:underline shrink-0">
                    {alert.actionLabel}
                  </Link>
                )}
              </AlertDescription>
            </Alert>
          ))}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Usage summary */}
        <div className="lg:col-span-2">
          <div className="rounded-lg border border-xelora-border bg-white p-5">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-semibold text-xelora-text">Usage this month</h2>
              <Link href="/dashboard/usage" className="text-xs text-xelora-info hover:underline">View details</Link>
            </div>
            {loading ? (
              <div className="space-y-4">
                {[1,2,3,4].map(i => <Skeleton key={i} className="h-10 w-full" />)}
              </div>
            ) : (
              <div className="space-y-4">
                {usageItems.map(({ label, used, limit, suffix }) => {
                  const pct = getUsagePercentage(used, limit);
                  const barColour = getUsageBarColour(pct);
                  return (
                    <div key={label}>
                      <div className="flex items-center justify-between mb-1.5 text-sm">
                        <span className="font-medium text-xelora-text">{label}</span>
                        <span className="text-xelora-text-secondary">{used} <span className="text-xelora-text-muted">/ {limit} {suffix}</span></span>
                      </div>
                      <Progress value={pct} className="h-2" indicatorClassName={barColour} aria-label={`${label}: ${pct}%`} />
                    </div>
                  );
                })}
              </div>
            )}
            {!loading && data && (
              <p className="mt-4 text-xs text-xelora-text-muted">Resets on {formatDate(data.usage.resetDate)}</p>
            )}
          </div>
        </div>

        {/* Plan card */}
        <div className="rounded-lg border border-xelora-border bg-white p-5">
          <h2 className="text-base font-semibold text-xelora-text mb-4">Current plan</h2>
          {loading ? (
            <div className="space-y-3">
              <Skeleton className="h-6 w-32" />
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-9 w-full mt-4" />
            </div>
          ) : data ? (
            <>
              <div className="flex items-center gap-2 mb-3">
                <Badge variant="green" className="capitalize">{data.subscription.planTier}</Badge>
                <Badge variant={data.subscription.status === 'active' ? 'success' : 'warning'}>
                  {data.subscription.status}
                </Badge>
              </div>
              <div className="space-y-1.5 text-sm text-xelora-text-secondary mb-5">
                <p>Renews {formatDate(data.subscription.currentPeriodEnd)}</p>
                <p className="capitalize">{data.subscription.billingCycle} billing</p>
              </div>
              <Button variant="outline" size="sm" className="w-full" asChild>
                <Link href="/dashboard/billing">Manage plan</Link>
              </Button>
            </>
          ) : null}
        </div>
      </div>

      {/* Recent files */}
      <div className="rounded-lg border border-xelora-border bg-white">
        <div className="flex items-center justify-between px-5 py-4 border-b border-xelora-border">
          <h2 className="text-base font-semibold text-xelora-text">Recent files</h2>
          <Link href="/dashboard/files" className="text-xs text-xelora-info hover:underline">View all</Link>
        </div>
        {loading ? (
          <div className="p-5 space-y-3">
            {[1,2,3,4].map(i => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" role="table">
              <thead>
                <tr className="border-b border-xelora-border bg-xelora-surface-2">
                  <th className="px-5 py-3 text-left font-medium text-xelora-text-secondary">Name</th>
                  <th className="px-4 py-3 text-left font-medium text-xelora-text-secondary hidden sm:table-cell">Type</th>
                  <th className="px-4 py-3 text-left font-medium text-xelora-text-secondary hidden md:table-cell">Size</th>
                  <th className="px-4 py-3 text-left font-medium text-xelora-text-secondary">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-xelora-text-secondary hidden lg:table-cell">Modified</th>
                  <th className="px-4 py-3 text-right font-medium text-xelora-text-secondary">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-xelora-border">
                {data?.recentFiles.map(file => {
                  const statusCfg = fileStatusBadge[file.status] ?? fileStatusBadge.ready;
                  return (
                    <tr key={file.id} className="hover:bg-xelora-surface-2 transition-colors">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2">
                          <FileSpreadsheet className="h-4 w-4 text-xelora-green shrink-0" aria-hidden="true" />
                          <span className="font-medium text-xelora-text truncate max-w-[160px]">{file.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell text-xelora-text-secondary uppercase text-xs">{file.type}</td>
                      <td className="px-4 py-3 hidden md:table-cell text-xelora-text-secondary">{formatFileSize(file.sizeMB)}</td>
                      <td className="px-4 py-3">
                        <Badge variant={statusCfg.variant}>{statusCfg.label}</Badge>
                      </td>
                      <td className="px-4 py-3 hidden lg:table-cell text-xelora-text-secondary">{formatRelativeTime(file.lastModifiedAt)}</td>
                      <td className="px-4 py-3 text-right">
                        <Button variant="ghost" size="sm" asChild>
                          <Link href={`/dashboard/files/${file.id}`} aria-label={`Open ${file.name}`}>
                            <ExternalLink className="h-3.5 w-3.5" />
                          </Link>
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Recent workflow runs */}
      <div className="rounded-lg border border-xelora-border bg-white">
        <div className="flex items-center justify-between px-5 py-4 border-b border-xelora-border">
          <h2 className="text-base font-semibold text-xelora-text">Recent workflow runs</h2>
          <Link href="/dashboard/history" className="text-xs text-xelora-info hover:underline">View all</Link>
        </div>
        {loading ? (
          <div className="p-5 space-y-3">
            {[1,2,3].map(i => <Skeleton key={i} className="h-16 w-full" />)}
          </div>
        ) : (
          <div className="divide-y divide-xelora-border">
            {data?.recentRuns.map(run => {
              const cfg = statusConfig[run.status] ?? statusConfig.completed;
              const StatusIcon = cfg.icon;
              return (
                <div key={run.id} className="flex items-center gap-4 px-5 py-4 hover:bg-xelora-surface-2 transition-colors">
                  <StatusIcon className={`h-4 w-4 shrink-0 ${cfg.colour}`} aria-hidden="true" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-xelora-text truncate">{run.workflowName}</p>
                    <p className="text-xs text-xelora-text-secondary">{run.fileName} · {run.stepsCompleted}/{run.totalSteps} steps · {run.aiActionsUsed} AI actions</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className={`text-xs font-medium ${cfg.colour}`}>{cfg.label}</p>
                    <p className="text-xs text-xelora-text-muted">{formatRelativeTime(run.startedAt)}</p>
                  </div>
                  <Button variant="ghost" size="sm" asChild>
                    <Link href={`/dashboard/history/${run.id}`} aria-label={`View run details for ${run.workflowName}`}>
                      <ExternalLink className="h-3.5 w-3.5" />
                    </Link>
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
