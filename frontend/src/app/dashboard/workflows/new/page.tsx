'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Plus, Trash2, Save, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { createWorkflow } from '@/services/workspace';
import type { WorkflowStepItem } from '@/services/workspace';

const STEP_TYPES = ['analyse', 'filter', 'clean', 'transform', 'formula', 'sort', 'deduplicate', 'format', 'chart', 'report', 'export', 'approval', 'condition', 'custom'];

const DEFAULT_STEPS: WorkflowStepItem[] = [
  { name: 'Analyse workbook', description: 'Detect structure and validate required columns.', type: 'analyse', isEnabled: true, requiresApproval: false, errorBehaviour: 'stop', estimatedAiActions: 2 },
  { name: 'Remove duplicate rows', description: 'Identify and remove duplicate entries.', type: 'deduplicate', isEnabled: true, requiresApproval: false, errorBehaviour: 'skip', estimatedAiActions: 3 },
  { name: 'Export workbook', description: 'Save the completed file as XLSX.', type: 'export', isEnabled: true, requiresApproval: false, errorBehaviour: 'stop', estimatedAiActions: 1 },
];

export default function NewWorkflowPage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [steps, setSteps] = useState<WorkflowStepItem[]>(DEFAULT_STEPS);
  const [isSaving, setIsSaving] = useState(false);

  const updateStep = (index: number, patch: Partial<WorkflowStepItem>) => {
    setSteps((current) => current.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  };

  const addStep = () => {
    setSteps((current) => [
      ...current,
      { name: 'New step', description: '', type: 'custom', isEnabled: true, requiresApproval: false, errorBehaviour: 'stop', estimatedAiActions: 1 },
    ]);
  };

  const removeStep = (index: number) => {
    setSteps((current) => current.filter((_, i) => i !== index));
  };

  const handleSave = async () => {
    if (!name.trim()) {
      toast.error('Give the workflow a name first.');
      return;
    }
    if (steps.length === 0) {
      toast.error('Add at least one step.');
      return;
    }
    setIsSaving(true);
    try {
      const w = await createWorkflow({ name: name.trim(), description, steps });
      toast.success(`'${w.name}' saved.`);
      router.push(`/dashboard/workflows/${w.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not save workflow.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Workflows"
        title="New workflow"
        description="Define the steps once, then run this workflow whenever you need it - each run submits a real instruction to the AI agent."
        actions={
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? <Zap className="h-4 w-4 animate-pulse" /> : <Save className="h-4 w-4" />}
            Save workflow
          </Button>
        }
      />

      <Card className="space-y-4 p-5">
        <div className="space-y-2">
          <Label htmlFor="wf-name">Name</Label>
          <Input id="wf-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Monthly revenue cleanup" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="wf-desc">Description</Label>
          <Textarea id="wf-desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} placeholder="What does this workflow do?" />
        </div>
      </Card>

      <div className="space-y-3">
        {steps.map((step, index) => (
          <Card key={index} className="space-y-3 p-4">
            <div className="flex items-start gap-3">
              <span className="mt-2 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-xelora-surface-2 text-xs font-semibold text-xelora-text-secondary">
                {index + 1}
              </span>
              <div className="flex-1 space-y-2">
                <Input value={step.name} onChange={(e) => updateStep(index, { name: e.target.value })} placeholder="Step name" />
                <Textarea value={step.description} onChange={(e) => updateStep(index, { description: e.target.value })} rows={2} placeholder="Step description" />
                <div className="flex flex-wrap items-center gap-3">
                  <Select value={step.type} onValueChange={(v) => updateStep(index, { type: v })}>
                    <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {STEP_TYPES.map((t) => <SelectItem key={t} value={t} className="capitalize">{t}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <div className="flex items-center gap-2">
                    <Switch checked={step.isEnabled} onCheckedChange={(v) => updateStep(index, { isEnabled: v })} />
                    <span className="text-xs text-xelora-text-secondary">Enabled</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch checked={step.requiresApproval} onCheckedChange={(v) => updateStep(index, { requiresApproval: v })} />
                    <span className="text-xs text-xelora-text-secondary">Requires approval</span>
                  </div>
                </div>
              </div>
              <Button variant="ghost" size="icon" className="text-xelora-error" onClick={() => removeStep(index)} aria-label="Remove step">
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </Card>
        ))}
        <Button variant="outline" onClick={addStep}>
          <Plus className="h-4 w-4" /> Add step
        </Button>
      </div>
    </div>
  );
}
