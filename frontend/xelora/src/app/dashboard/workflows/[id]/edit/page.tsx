'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Plus, Save, PlayCircle, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { StatePanel } from '@/components/site/state-panel';
import { getWorkflowById, runWorkflow, updateWorkflow, type WorkflowItem, type WorkflowStepItem } from '@/services/workspace';
import type { StepType } from '@/types';

type DraftStep = WorkflowStepItem & { localId: string };

function toPersistedStep(step: DraftStep): WorkflowStepItem {
  return {
    name: step.name,
    description: step.description,
    type: step.type,
    isEnabled: step.isEnabled,
    requiresApproval: step.requiresApproval,
    errorBehaviour: step.errorBehaviour,
    estimatedAiActions: step.estimatedAiActions,
  };
}

export default function EditWorkflowPage() {
  const params = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [steps, setSteps] = useState<DraftStep[]>([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [workflow, setWorkflow] = useState<WorkflowItem | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    getWorkflowById(params.id).then((item) => {
      setWorkflow(item); setName(item.name); setDescription(item.description);
      setSteps(item.steps.map((step, index) => ({ ...step, localId: `${index}-${step.name}` })));
    }).catch((err) => setError(err instanceof Error ? err.message : 'Workflow not found.')).finally(() => setLoading(false));
  }, [params.id]);

  const addStep = () => {
    setSteps((current) => [
      ...current,
      {
        localId: `local-${Date.now()}`,
        name: 'New step',
        description: '',
        type: 'custom',
        isEnabled: true,
        requiresApproval: false,
        errorBehaviour: 'skip',
        estimatedAiActions: 2,
      },
    ]);
  };

  if (!loading && !workflow) {
    return <StatePanel kind="empty" title="Workflow not found" description={error || 'This workflow does not exist.'} />;
  }

  if (loading || !workflow) {
    return <StatePanel kind="loading" title="Loading workflow editor" description="Preparing the editable workflow builder." />;
  }

  const updateStep = (localId: string, updates: Partial<DraftStep>) => {
    setSteps((current) => current.map((step) => (step.localId === localId ? { ...step, ...updates } : step)));
  };

  const removeStep = (localId: string) => {
    setSteps((current) => current.filter((step) => step.localId !== localId));
  };

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Workflows"
        title={`Editing ${workflow.name}`}
        description="Adjust the persisted workflow and save your changes."
        actions={
          <>
            <Button variant="outline" onClick={() => runWorkflow(workflow.id).then(() => toast.success('Test run started.')).catch((err) => toast.error(err.message))}>
              <PlayCircle className="h-4 w-4" />
              Test run
            </Button>
            <Button onClick={() => updateWorkflow(workflow.id, { name, description, steps: steps.map(toPersistedStep), tags: workflow.tags }).then(setWorkflow).then(() => toast.success('Workflow saved.')).catch((err) => toast.error(err.message))}><Save className="h-4 w-4" />Save draft</Button>
          </>
        }
      />

      <Card className="p-5 space-y-4">
        <div>
          <Label>Workflow name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <Label>Description</Label>
          <Textarea value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
      </Card>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-xelora-text">Steps</h2>
          <Button variant="outline" onClick={addStep}>
            <Plus className="h-4 w-4" />
            Add step
          </Button>
        </div>
        {steps.map((step) => (
          <Card key={step.localId} className="p-5">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>Step name</Label>
                <Input value={step.name} onChange={(e) => updateStep(step.localId, { name: e.target.value })} />
              </div>
              <div>
                <Label>Type</Label>
                <Select value={step.type} onValueChange={(value) => updateStep(step.localId, { type: value as StepType })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {['analyse', 'clean', 'deduplicate', 'transform', 'formula', 'sort', 'format', 'chart', 'report', 'export', 'approval', 'condition', 'custom'].map((value) => (
                      <SelectItem key={value} value={value}>{value}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="md:col-span-2">
                <Label>Description</Label>
                <Textarea value={step.description ?? ''} onChange={(e) => updateStep(step.localId, { description: e.target.value })} />
              </div>
              <div className="flex items-center justify-between md:col-span-2">
                <div className="flex items-center gap-2">
                  <Switch checked={step.isEnabled} onCheckedChange={(checked) => updateStep(step.localId, { isEnabled: checked })} />
                  <Label className="font-normal">Enable step</Label>
                </div>
                <Button variant="ghost" className="text-xelora-error" onClick={() => removeStep(step.localId)}>
                  <Trash2 className="h-4 w-4" />
                  Remove
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
