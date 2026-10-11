'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { LayoutTemplate, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';
import { getTemplates, useTemplate as applyTemplateApi } from '@/services/workspace';
import type { WorkflowTemplateItem } from '@/services/workspace';

export default function TemplatesPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<WorkflowTemplateItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [applyingId, setApplyingId] = useState<string | null>(null);

  useEffect(() => {
    getTemplates()
      .then(setTemplates)
      .catch((err) => toast.error(err instanceof Error ? err.message : 'Could not load templates.'))
      .finally(() => setLoading(false));
  }, []);

  const handleUse = async (t: WorkflowTemplateItem) => {
    setApplyingId(t.id);
    try {
      const workflow = await applyTemplateApi(t.id);
      toast.success(`'${t.name}' added to your workflows.`);
      router.push(`/dashboard/workflows/${workflow.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not use this template.');
    } finally {
      setApplyingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Templates"
        title="Workflow templates"
        description="Start from a ready-made template instead of building a workflow from scratch."
      />

      {loading ? (
        <StatePanel kind="loading" title="Loading templates" description="Fetching workflow templates." />
      ) : templates.length === 0 ? (
        <StatePanel kind="empty" title="No templates available" description="Check back later." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {templates.map((t) => (
            <Card key={t.id} className="p-5">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-xelora-surface-2">
                  <LayoutTemplate className="h-5 w-5 text-xelora-green" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-xelora-text">{t.name}</h3>
                  <Badge variant="outline" className="mt-1 capitalize">{t.category}</Badge>
                </div>
              </div>
              <p className="mt-3 text-sm text-xelora-text-secondary">{t.description}</p>
              <p className="mt-3 text-xs text-xelora-text-muted">{t.steps.length} step{t.steps.length === 1 ? '' : 's'}</p>
              <Button className="mt-4 w-full" onClick={() => handleUse(t)} disabled={applyingId === t.id}>
                {applyingId === t.id ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Use this template
              </Button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
