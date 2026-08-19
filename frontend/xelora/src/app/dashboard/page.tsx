'use client';
;
import Link from 'next/link';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, Bot, CheckCircle2, FileSpreadsheet, FolderOpen, Play, Plus, Sparkles, Workflow } from 'lucide-react';
import { useAuthStore } from '@/stores/auth-store';
import { mockFiles } from '@/data/mock-files';
import { mockUsage } from '@/data/mock-usage';
import { mockWorkflowRuns, mockWorkflows } from '@/data/mock-workflows';<q></q>
import { formatFileSize, formatRelativeTime, getUsagePercentage } from '@/lib/utils';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { isDesktopApp } from '@/lib/is-desktop';

const runStatus: Record<string, { label: string; variant: 'success' | 'warning' | 'info' }> = {
  completed: { label: 'Completed', variant: 'success' },
  completed_with_warnings: { label: 'Needs review', variant: 'warning' },
  running: { label: 'Running', variant: 'info' },
};

export default function DashboardIndexPage() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const firstName = user?.name?.split(' ')[0] || 'there';
  const recentFiles = mockFiles.slice(0, 4);
  const recentRuns = mockWorkflowRuns.slice(0, 3);
  const aiUsage = getUsagePercentage(mockUsage.aiActionsUsed, mockUsage.aiActionsLimit);
  const workflowUsage = getUsagePercentage(mockUsage.workflowRunsUsed, mockUsage.workflowRunsLimit);

  useEffect(() => {
    if (isDesktopApp()) router.replace('/dashboard/agent?new=1');
  }, [router]);

  return <div className="mx-auto max-w-7xl space-y-6">
    <DashboardPageHeader eyebrow="Workspace overview" title={`Welcome back, ${firstName}`} description="Here is what is happening across your files, workflows, and automations." actions={<><Button variant="outline" asChild><Link href="/dashboard/files"><FolderOpen className="h-4 w-4" />Open files</Link></Button><Button asChild><Link href="/dashboard/agent?new=1"><Sparkles className="h-4 w-4" />Ask Xelora</Link></Button></>} />

    <Card className="overflow-hidden border-xelora-deep-green bg-xelora-deep-green text-white"><div className="grid gap-6 px-6 py-7 md:grid-cols-[minmax(0,1fr)_auto] md:items-center sm:px-8"><div><p className="text-sm font-medium text-xelora-bright-green">Your workspace is ready</p><h2 className="mt-2 text-2xl font-semibold tracking-tight">What would you like to accomplish?</h2><p className="mt-2 max-w-xl text-sm leading-6 text-white/75">Start a new AI task for a workbook, create an automation, or continue working with your files.</p></div><div className="flex flex-wrap gap-3"><Button variant="bright" asChild><Link href="/dashboard/agent?new=1"><Bot className="h-4 w-4" />New AI task</Link></Button><Button className="border border-white/20 bg-white/10 text-white hover:bg-white/20" asChild><Link href="/dashboard/workflows/new"><Plus className="h-4 w-4" />New workflow</Link></Button></div></div></Card>

    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Card className="p-5"><div className="flex items-center justify-between"><span className="text-sm text-xelora-text-secondary">Files in workspace</span><FileSpreadsheet className="h-4 w-4 text-xelora-green" /></div><p className="mt-3 text-2xl font-semibold text-xelora-text">{mockFiles.length}</p><p className="mt-1 text-xs text-xelora-text-muted">{mockFiles.filter((file) => file.status === 'needs_review').length} need your review</p></Card><Card className="p-5"><div className="flex items-center justify-between"><span className="text-sm text-xelora-text-secondary">Active workflows</span><Workflow className="h-4 w-4 text-xelora-green" /></div><p className="mt-3 text-2xl font-semibold text-xelora-text">{mockWorkflows.filter((workflow) => workflow.status === 'published').length}</p><p className="mt-1 text-xs text-xelora-text-muted">Ready to run when you are</p></Card><Card className="p-5"><div className="flex items-center justify-between"><span className="text-sm text-xelora-text-secondary">AI actions</span><Sparkles className="h-4 w-4 text-xelora-green" /></div><p className="mt-3 text-2xl font-semibold text-xelora-text">{mockUsage.aiActionsUsed.toLocaleString()} <span className="text-sm font-normal text-xelora-text-muted">/ {mockUsage.aiActionsLimit.toLocaleString()}</span></p><Progress value={aiUsage} className="mt-3 h-1.5 bg-xelora-surface-2" indicatorClassName="bg-xelora-green" /></Card><Card className="p-5"><div className="flex items-center justify-between"><span className="text-sm text-xelora-text-secondary">Workflow runs</span><Play className="h-4 w-4 text-xelora-green" /></div><p className="mt-3 text-2xl font-semibold text-xelora-text">{mockUsage.workflowRunsUsed} <span className="text-sm font-normal text-xelora-text-muted">/ {mockUsage.workflowRunsLimit}</span></p><Progress value={workflowUsage} className="mt-3 h-1.5 bg-xelora-surface-2" indicatorClassName="bg-xelora-green" /></Card></div>

    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(290px,0.8fr)]"><Card><div className="flex items-center justify-between border-b border-xelora-border px-5 py-4"><div><h2 className="font-semibold text-xelora-text">Recent files</h2><p className="mt-0.5 text-sm text-xelora-text-secondary">Your latest workbook activity.</p></div><Link href="/dashboard/files" className="inline-flex items-center gap-1 text-sm font-medium text-xelora-green hover:underline">View all <ArrowRight className="h-4 w-4" /></Link></div><div className="divide-y divide-xelora-border">{recentFiles.map((file) => <Link href={`/dashboard/files/${file.id}`} key={file.id} className="flex items-center gap-3 px-5 py-4 transition-colors hover:bg-xelora-surface-2"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-xelora-success-bg text-xelora-green"><FileSpreadsheet className="h-4 w-4" /></span><span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium text-xelora-text">{file.name}</span><span className="mt-0.5 block text-xs text-xelora-text-muted">{formatFileSize(file.sizeMB * 1024 * 1024)} · Updated {formatRelativeTime(file.lastModifiedAt)}</span></span><Badge variant={file.status === 'needs_review' ? 'warning' : file.status === 'processing' ? 'info' : 'success'}>{file.status === 'needs_review' ? 'Review' : file.status === 'processing' ? 'Processing' : 'Ready'}</Badge></Link>)}</div></Card>
      <Card><div className="border-b border-xelora-border px-5 py-4"><h2 className="font-semibold text-xelora-text">Continue working</h2><p className="mt-0.5 text-sm text-xelora-text-secondary">Pick up where you left off.</p></div><div className="space-y-2 p-3"><Link href="/dashboard/agent?new=1" className="flex items-center gap-3 rounded-lg p-3 transition-colors hover:bg-xelora-surface-2"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-xelora-success-bg text-xelora-green"><Bot className="h-4 w-4" /></span><span><span className="block text-sm font-medium text-xelora-text">Start an AI task</span><span className="block text-xs text-xelora-text-muted">Ask for help with any workbook.</span></span></Link><Link href="/dashboard/templates" className="flex items-center gap-3 rounded-lg p-3 transition-colors hover:bg-xelora-surface-2"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-xelora-info-bg text-xelora-info"><Workflow className="h-4 w-4" /></span><span><span className="block text-sm font-medium text-xelora-text">Use a template</span><span className="block text-xs text-xelora-text-muted">Start from a proven workflow.</span></span></Link><Link href="/dashboard/help" className="flex items-center gap-3 rounded-lg p-3 transition-colors hover:bg-xelora-surface-2"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-xelora-warning-bg text-xelora-warning"><CheckCircle2 className="h-4 w-4" /></span><span><span className="block text-sm font-medium text-xelora-text">Get help</span><span className="block text-xs text-xelora-text-muted">Browse guides and support options.</span></span></Link></div></Card></div>

    <Card><div className="flex items-center justify-between border-b border-xelora-border px-5 py-4"><div><h2 className="font-semibold text-xelora-text">Recent workflow activity</h2><p className="mt-0.5 text-sm text-xelora-text-secondary">The latest work completed in your workspace.</p></div><Link href="/dashboard/history" className="text-sm font-medium text-xelora-green hover:underline">View history</Link></div><div className="divide-y divide-xelora-border">{recentRuns.map((run) => { const status = runStatus[run.status] ?? runStatus.running; return <Link key={run.id} href="/dashboard/history" className="flex flex-col gap-2 px-5 py-4 transition-colors hover:bg-xelora-surface-2 sm:flex-row sm:items-center"><span className="min-w-0 flex-1"><span className="block text-sm font-medium text-xelora-text">{run.workflowName}</span><span className="mt-0.5 block truncate text-xs text-xelora-text-muted">{run.fileName} · {formatRelativeTime(run.completedAt ?? run.startedAt)}</span></span><span className="text-xs text-xelora-text-muted">{run.stepsCompleted}/{run.totalSteps} steps</span><Badge variant={status.variant}>{status.label}</Badge></Link>; })}</div></Card>
  </div>;
}
