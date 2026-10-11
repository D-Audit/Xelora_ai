'use client';

import { useEffect, useMemo, useState } from 'react';
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
import { mockWorkflows } from '@/data/mock-workflows';
import type { WorkflowStep, StepType } from '@/types';

type DraftStep = WorkflowStep & { localId: string };

export default function EditWorkflowPage() {
  const params = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [steps, setSteps] = useState<DraftStep[]>([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const workflow = useMemo(() => mockWorkflows.find((item) => item.id === params.id), [params.id]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (workflow) {
        setName(workflow.name);
        setDescription(workflow.description);
        setSteps(workflow.steps.map((step) => ({ ...step, localId: step.id })));
      }
      setLoading(false);
    }, 400);
    return () => clearTimeout(timer);
  }, [workflow]);

  const addStep = () => {
    setSteps((current) => [
      ...current,
      {
        localId: `local-${Date.now()}`,
        id: `local-${Date.now()}`,
        workflowId: workflow?.id ?? 'draft',
        order: current.length + 1,
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
    return <StatePanel kind="empty" title="Workflow not found" description="This workflow is not part of the mock dataset." />;
  }

  if (loading || !workflow) {
    return <StatePanel kind="loading" title="Loading workflow editor" description="Preparing the editable workflow builder." />;
  }

  const updateStep = (localId: string, updates: Partial<DraftStep>) => {
    setSteps((current) => current.map((step) => (step.localId === localId ? { ...step, ...updates } : step)));
  };

  const removeStep = (localId: string) => {
    setSteps((current) => current.filter((step) => step.localId !== localId).map((step, index) => ({ ...step, order: index + 1 })));
  };

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Workflows"
        title={`Editing ${workflow.name}`}
        description="Adjust the mock workflow and save it as a draft."
        actions={
          <>
            <Button variant="outline" onClick={() => toast.info('Test run completed with mock data.')}>
              <PlayCircle className="h-4 w-4" />
              Test run
            </Button>
            <Button onClick={() => toast.success('Workflow saved.')}><Save className="h-4 w-4" />Save draft</Button>
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
