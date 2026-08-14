import type { UsageLimits, DailyUsage } from '@/types';

export const mockUsage: UsageLimits = {
  aiActionsUsed: 420,
  aiActionsLimit: 1500,
  workflowRunsUsed: 32,
  workflowRunsLimit: 300,
  storageUsedGB: 4.2,
  storageLimitGB: 20,
  devicesUsed: 2,
  devicesLimit: 3,
  teamMembersUsed: 3,
  teamMembersLimit: 5,
  resetDate: '2026-08-15T00:00:00Z',
};

export const mockDailyUsage: DailyUsage[] = [
  { date: '2026-07-11', aiActions: 18, workflowRuns: 2, fileOperations: 4 },
  { date: '2026-07-12', aiActions: 24, workflowRuns: 3, fileOperations: 5 },
  { date: '2026-07-13', aiActions: 12, workflowRuns: 1, fileOperations: 2 },
  { date: '2026-07-14', aiActions: 31, workflowRuns: 4, fileOperations: 7 },
  { date: '2026-07-15', aiActions: 22, workflowRuns: 2, fileOperations: 3 },
  { date: '2026-07-16', aiActions: 8, workflowRuns: 1, fileOperations: 1 },
  { date: '2026-07-17', aiActions: 5, workflowRuns: 0, fileOperations: 1 },
  { date: '2026-07-18', aiActions: 38, workflowRuns: 4, fileOperations: 6 },
  { date: '2026-07-19', aiActions: 44, workflowRuns: 5, fileOperations: 8 },
  { date: '2026-07-20', aiActions: 29, workflowRuns: 3, fileOperations: 4 },
  { date: '2026-07-21', aiActions: 52, workflowRuns: 6, fileOperations: 9 },
  { date: '2026-07-22', aiActions: 41, workflowRuns: 4, fileOperations: 7 },
  { date: '2026-07-23', aiActions: 36, workflowRuns: 3, fileOperations: 6 },
  { date: '2026-07-24', aiActions: 60, workflowRuns: 5, fileOperations: 10 },
];

export const mockUsageByOperation = [
  { operation: 'Data Cleaning', aiActions: 142 },
  { operation: 'Formula Gen', aiActions: 98 },
  { operation: 'Deduplication', aiActions: 76 },
  { operation: 'Reporting', aiActions: 64 },
  { operation: 'Analysis', aiActions: 40 },
];
