import type { AdminStats, DesktopRelease, SystemService, User } from '@/types';
import { mockUsers } from '@/data/mock-users';

export const mockAdminStats: AdminStats = {
  totalUsers: 14820,
  activeSubscriptions: 3812,
  trialConversions: 21,
  monthlyRecurringRevenue: 428000,
  aiActionsToday: 18420,
  workflowRunsToday: 3120,
  totalStorageGB: 8942,
  failedOperationsToday: 14,
};

export const mockAdminUsers: User[] = mockUsers;

export const mockAdminPlanRows = [
  { plan: 'Starter', monthlyPrice: 12, annualPrice: 9, status: 'active', users: 9120 },
  { plan: 'Professional', monthlyPrice: 35, annualPrice: 28, status: 'active', users: 3610 },
  { plan: 'Business', monthlyPrice: 'Custom', annualPrice: 'Custom', status: 'sales-led', users: 82 },
];

export const mockAdminReleases: DesktopRelease[] = [
  {
    id: 'release-130',
    version: '1.3.0',
    os: 'windows',
    status: 'stable',
    releasedAt: '2026-07-20T00:00:00Z',
    fileSizeMB: 84,
    downloadCount: 18420,
    releaseNotes: ['Workflow preview polish', 'Batch processing speed improvements', 'Formula rendering fixes'],
    downloadUrl: '#',
    checksum: 'SHA-256: 7E2F-9C8A-4F31-2E90-4B4C-91F2-8C91-2AB3',
  },
  {
    id: 'release-129',
    version: '1.2.9',
    os: 'windows',
    status: 'deprecated',
    releasedAt: '2026-06-10T00:00:00Z',
    fileSizeMB: 82,
    downloadCount: 13214,
    releaseNotes: ['Stability improvements'],
  },
];

export const mockSystemServices: SystemService[] = [
  { name: 'Authentication', status: 'operational', latencyMs: 42, uptime: 99.98, lastCheckedAt: '2026-07-24T09:00:00Z' },
  { name: 'Billing', status: 'operational', latencyMs: 61, uptime: 99.95, lastCheckedAt: '2026-07-24T09:00:00Z' },
  { name: 'AI service', status: 'degraded', latencyMs: 220, uptime: 99.1, lastCheckedAt: '2026-07-24T09:00:00Z' },
  { name: 'File processing', status: 'operational', latencyMs: 74, uptime: 99.89, lastCheckedAt: '2026-07-24T09:00:00Z' },
  { name: 'Cloud storage', status: 'maintenance', latencyMs: undefined, uptime: 99.6, lastCheckedAt: '2026-07-24T09:00:00Z' },
  { name: 'Notifications', status: 'operational', latencyMs: 35, uptime: 99.99, lastCheckedAt: '2026-07-24T09:00:00Z' },
];
