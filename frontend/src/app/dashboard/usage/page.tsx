'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { BarChart3, LineChart, ShoppingCart, Zap } from 'lucide-react';
import {
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  LineChart as ReLineChart,
  Line,
  BarChart as ReBarChart,
  Bar,
} from 'recharts';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';
import { getUsage } from '@/services/dashboard';
import { mockUsageByOperation } from '@/data/mock-usage';
import { formatDate } from '@/lib/utils';
import type { UsageLimits } from '@/types';

type UsageSummary = UsageLimits;

export default function UsagePage() {
  const [loading, setLoading] = useState(true);
  const [daily, setDaily] = useState<{ date: string; aiActions: number; workflowRuns: number; fileOperations: number }[]>([]);
  const [summary, setSummary] = useState<UsageSummary | null>(null);

  useEffect(() => {
    getUsage().then((data) => {
      setSummary(data.summary);
      setDaily(data.daily);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <StatePanel kind="loading" title="Loading usage" description="Preparing chart data and summary metrics." />;
  }

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Usage"
        title="Track Xelora usage"
        description="Charts and summaries stay restrained so the monthly pattern is easy to scan."
        actions={<Button variant="outline" asChild><Link href="/dashboard/billing">Buy additional usage</Link></Button>}
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          { label: 'AI actions', value: `${summary?.aiActionsUsed ?? 0} / ${summary?.aiActionsLimit ?? 0}`, icon: Zap },
          { label: 'Workflow runs', value: `${summary?.workflowRunsUsed ?? 0} / ${summary?.workflowRunsLimit ?? 0}`, icon: BarChart3 },
          { label: 'Storage', value: `${summary?.storageUsedGB?.toFixed(1) ?? '0.0'} / ${summary?.storageLimitGB ?? 0} GB`, icon: LineChart },
          { label: 'Devices', value: `${summary?.devicesUsed ?? 0} / ${summary?.devicesLimit ?? 0}`, icon: ShoppingCart },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.label} className="p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-xelora-surface-2">
                  <Icon className="h-5 w-5 text-xelora-green" />
                </div>
                <div>
                  <p className="text-sm font-medium text-xelora-text">{item.label}</p>
                  <p className="text-sm text-xelora-text-secondary">{item.value}</p>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="text-base font-semibold text-xelora-text">Daily usage</h2>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ReLineChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" stroke="#DDE5E2" />
                <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#5C6C75' }} />
                <YAxis tick={{ fontSize: 12, fill: '#5C6C75' }} />
                <Tooltip />
                <Line type="monotone" dataKey="aiActions" stroke="#00684A" strokeWidth={2} dot={false} />
              </ReLineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-5">
          <h2 className="text-base font-semibold text-xelora-text">Usage by operation</h2>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ReBarChart data={mockUsageByOperation}>
                <CartesianGrid strokeDasharray="3 3" stroke="#DDE5E2" />
                <XAxis dataKey="operation" tick={{ fontSize: 12, fill: '#5C6C75' }} />
                <YAxis tick={{ fontSize: 12, fill: '#5C6C75' }} />
                <Tooltip />
                <Bar dataKey="aiActions" fill="#00ED64" radius={[4, 4, 0, 0]} />
              </ReBarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <div className="border-b border-xelora-border px-5 py-4">
          <h2 className="text-base font-semibold text-xelora-text">Recent usage</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-xelora-surface-2">
              <tr className="border-b border-xelora-border text-left">
                <th className="px-5 py-3 font-medium text-xelora-text-secondary">Date</th>
                <th className="px-4 py-3 font-medium text-xelora-text-secondary">AI actions</th>
                <th className="px-4 py-3 font-medium text-xelora-text-secondary">Workflow runs</th>
                <th className="px-4 py-3 font-medium text-xelora-text-secondary">File operations</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-xelora-border bg-white">
              {daily.slice(-7).map((item) => (
                <tr key={item.date}>
                  <td className="px-5 py-3 text-xelora-text-secondary">{formatDate(`${item.date}T00:00:00Z`)}</td>
                  <td className="px-4 py-3 text-xelora-text-secondary">{item.aiActions}</td>
                  <td className="px-4 py-3 text-xelora-text-secondary">{item.workflowRuns}</td>
                  <td className="px-4 py-3 text-xelora-text-secondary">{item.fileOperations}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
