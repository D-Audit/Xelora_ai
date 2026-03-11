'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Play, ArrowLeft, Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';
import { getWorkflowById, runWorkflow, getRunById } from '@/services/workspace';
import type { WorkflowItem, WorkflowRunItem } from '@/services/workspace';
import { formatRelativeTime } from '@/lib/utils';

const runStatusIcon: Record<string, typeof CheckCircle2> = {
  completed: CheckCircle2,
  failed: XCircle,
  running: Clock,
};

export default function WorkflowDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [workflow, setWorkflow] = useState<WorkflowItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [activeRun, setActiveRun] = useState<WorkflowRunItem | null>(null);

  useEffect(() => {
    getWorkflowById(id)
      .then(setWorkflow)
      .catch((err) => toast.error(err instanceof Error ? err.message : 'Could not load workflow.'))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!activeRun || activeRun.status !== 'running') return;
    const interval = setInterval(async () => {
      try {
        const updated = await getRunById(activeRun.id);
        setActiveRun(updated);
        if (updated.status !== 'running') {
          clearInterval(interval);
          getWorkflowById(id).then(setWorkflow).catch(() => {});
        }
      } catch {
        clearInterval(interval);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [activeRun, id]);

  const handleRun = async () => {
    setIsRunning(true);
    try {
      const run = await runWorkflow(id);
      setActiveRun(run);
      toast.success(`Started - task #${run.taskId}.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not start this workflow.');
    } finally {
      setIsRunning(false);
    }
  };

  if (loading) {
    return <StatePanel kind="loading" title="Loading workflow" description="Fetching workflow details." />;
  }
  if (!workflow) {
    return <StatePanel kind="empty" title="Workflow not found" description="It may have been deleted." />;
  }

  const StatusIcon = activeRun ? runStatusIcon[activeRun.status] ?? Clock : null;

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Workflows"
        title={workflow.name}
        description={workflow.description || 'No description.'}
        actions={
          <>
            <Button variant="outline" asChild>
              <Link href="/dashboard/workflows"><ArrowLeft className="h-4 w-4" /> Back</Link>
            </Button>
            <Button onClick={handleRun} disabled={isRunning || activeRun?.status === 'running'}>
              {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Run workflow
            </Button>
          </>
        }
      />

      {activeRun && (
        <Card className="flex items-center gap-3 p-4">
          {StatusIcon && <StatusIcon className={`h-5 w-5 ${activeRun.status === 'completed' ? 'text-xelora-success' : activeRun.status === 'failed' ? 'text-xelora-error' : 'text-xelora-info animate-pulse'}`} />}
          <div>
            <p className="text-sm font-medium text-xelora-text">
              Run #{activeRun.id} - task #{activeRun.taskId} - {activeRun.status}
            </p>
            <p className="text-xs text-xelora-text-muted">{activeRun.stepsCompleted} step(s) completed</p>
          </div>
        </Card>
      )}

      <Card className="p-5">
        <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
          <div>
            <p className="text-xs text-xelora-text-muted">Status</p>
            <Badge variant={workflow.status === 'published' ? 'success' : 'default'}>{workflow.status}</Badge>
          </div>
          <div>
            <p className="text-xs text-xelora-text-muted">Total runs</p>
            <p className="font-medium text-xelora-text">{workflow.totalRuns}</p>
          </div>
          <div>
            <p className="text-xs text-xelora-text-muted">Success rate</p>
            <p className="font-medium text-xelora-text">{workflow.successRate}%</p>
          </div>
          <div>
            <p className="text-xs text-xelora-text-muted">Last run</p>
            <p className="font-medium text-xelora-text">{workflow.lastRunAt ? formatRelativeTime(workflow.lastRunAt) : 'never'}</p>
          </div>
        </div>
      </Card>

      <Card className="p-5">
        <h2 className="text-base font-semibold text-xelora-text">Steps</h2>
        <div className="mt-3 space-y-2">
          {workflow.steps.map((step, i) => (
            <div key={i} className="flex items-start gap-3 rounded-lg border border-xelora-border p-3">
              <span className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-xelora-surface-2 text-xs font-semibold text-xelora-text-secondary">
                {i + 1}
              </span>
              <div>
                <p className="text-sm font-medium text-xelora-text">{step.name}</p>
                {step.description && <p className="text-xs text-xelora-text-muted">{step.description}</p>}
              </div>
              {!step.isEnabled && <Badge variant="default" className="ml-auto">Disabled</Badge>}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
