'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { ArrowDown, ArrowUp, Loader2, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { StatePanel } from '@/components/site/state-panel';
import { getWorkflowById, updateWorkflow, type WorkflowStepItem } from '@/services/workspace';

type DraftStep = WorkflowStepItem & { localId: string };

let nextLocalId = 0;
const withLocalId = (step: WorkflowStepItem): DraftStep => ({ ...step, localId: `s${nextLocalId++}` });

export default function EditWorkflowPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [state, setState] = useState<'loading' | 'ready' | 'missing'>('loading');
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [steps, setSteps] = useState<DraftStep[]>([]);

  useEffect(() => {
    getWorkflowById(params.id)
      .then((workflow) => {
        setName(workflow.name);
        setDescription(workflow.description ?? '');
        setSteps(workflow.steps.map(withLocalId));
        setState('ready');
      })
      .catch(() => setState('missing'));
  }, [params.id]);

  const update = (localId: string, changes: Partial<DraftStep>) =>
    setSteps((current) => current.map((step) => (step.localId === localId ? { ...step, ...changes } : step)));
  const move = (index: number, offset: number) =>
    setSteps((current) => {
      const next = [...current];
      const [step] = next.splice(index, 1);
      next.splice(index + offset, 0, step);
      return next;
    });
  const addStep = () => setSteps((current) => [...current, withLocalId({
    name: '', description: '', type: 'custom', isEnabled: true, requiresApproval: false, errorBehaviour: 'stop', estimatedAiActions: 1,
  })]);

  const save = async () => {
    if (!name.trim()) return toast.error('Give the workflow a name.');
    if (steps.some((step) => !step.name.trim())) return toast.error('Every step needs an instruction.');
    setSaving(true);
    try {
      await updateWorkflow(params.id, {
        name: name.trim(),
        description: description.trim(),
        steps: steps.map((step) => ({
          name: step.name, description: step.description, type: step.type, isEnabled: step.isEnabled,
          requiresApproval: step.requiresApproval, errorBehaviour: step.errorBehaviour, estimatedAiActions: step.estimatedAiActions,
        })),
      });
      toast.success('Workflow saved.');
      router.push(`/dashboard/workflows/${params.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not save the workflow.');
    } finally {
      setSaving(false);
    }
  };

  if (state === 'loading') return <StatePanel kind="loading" title="Loading workflow" description="" />;
  if (state === 'missing') {
    return <StatePanel kind="empty" title="Workflow not found" description="It may have been deleted." />;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <DashboardPageHeader
        title="Edit workflow"
        description="Each step is an instruction Xelora carries out in order when the workflow runs."
        actions={
          <>
            <Button variant="ghost" asChild><Link href={`/dashboard/workflows/${params.id}`}>Cancel</Link></Button>
            <Button onClick={() => void save()} disabled={saving}>{saving && <Loader2 className="h-4 w-4 animate-spin" />} Save</Button>
          </>
        }
      />

      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="wf-name">Name</Label>
          <Input id="wf-name" value={name} onChange={(event) => setName(event.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="wf-description">Description</Label>
          <Textarea id="wf-description" value={description} onChange={(event) => setDescription(event.target.value)} rows={2} />
        </div>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-xelora-text">Steps</h2>
        <ol className="space-y-3">
          {steps.map((step, index) => (
            <li key={step.localId} className="rounded-xl border border-xelora-border bg-xelora-surface p-4">
              <div className="flex items-start gap-3">
                <span className="mt-2 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-xelora-border text-xs font-medium text-xelora-text-secondary">{index + 1}</span>
                <div className="flex-1 space-y-3">
                  <Input value={step.name} onChange={(event) => update(step.localId, { name: event.target.value })} placeholder="What should Xelora do? For example: Remove duplicate rows" aria-label={`Step ${index + 1} instruction`} />
                  <Textarea value={step.description ?? ''} onChange={(event) => update(step.localId, { description: event.target.value })} placeholder="Details (optional)" rows={2} aria-label={`Step ${index + 1} details`} />
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-wrap items-center gap-5 text-sm text-xelora-text-secondary">
                      <label className="flex items-center gap-2"><Switch checked={step.isEnabled} onCheckedChange={(checked) => update(step.localId, { isEnabled: checked })} /> Enabled</label>
                      <label className="flex items-center gap-2"><Switch checked={step.requiresApproval} onCheckedChange={(checked) => update(step.localId, { requiresApproval: checked })} /> Ask before running</label>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="icon-sm" onClick={() => move(index, -1)} disabled={index === 0} aria-label="Move step up"><ArrowUp className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon-sm" onClick={() => move(index, 1)} disabled={index === steps.length - 1} aria-label="Move step down"><ArrowDown className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon-sm" className="text-xelora-error hover:text-xelora-error" onClick={() => setSteps((current) => current.filter((item) => item.localId !== step.localId))} aria-label="Remove step"><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ol>
        <Button variant="outline" onClick={addStep}><Plus className="h-4 w-4" /> Add step</Button>
      </section>
    </div>
  );
}
