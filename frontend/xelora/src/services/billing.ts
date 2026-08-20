/**
 * Client-side billing service. Calls our own Next.js API routes.
 * Return shapes are kept close to the mock-billing.ts / mock-plans.ts
 * shapes the existing pages were built against, to minimise page
 * rewrites - see PlanSummary/SubscriptionSummary below.
 */

export interface PlanSummary {
  tier: string;
  name: string;
  description: string;
  monthlyPrice: number | null;
  annualPrice: number | null;
  limits: {
    aiActionsPerMonth: number | 'custom';
    workflowRunsPerMonth: number | 'custom';
    maxFileSizeMB: number | 'custom';
    savedWorkflows: number | 'custom';
    cloudStorageGB: number | 'custom';
    devices: number | 'custom';
    historyDays: number | 'custom';
    teamMembers: number | 'custom';
    batchProcessing: boolean;
    apiAccess: boolean;
    prioritySupport: boolean;
  };
}

export interface SubscriptionSummary {
  id: string;
  planTier: string;
  billingCycle: string;
  status: string;
  currentPeriodStart: string | null;
  currentPeriodEnd: string | null;
  cancelAtPeriodEnd: boolean;
  trialEndsAt: string | null;
}

export interface UsageSummary {
  aiActionsUsed: number;
  aiActionsLimit: number | 'unlimited';
  workflowRunsUsed: number;
  workflowRunsLimit: number | 'unlimited';
  resetDate: string | null;
}

export interface DetailedUsageSummary extends UsageSummary {
  storageUsedGB: number;
  storageLimitGB: number | 'unlimited';
  devicesUsed: number;
  devicesLimit: number | 'unlimited';
}

export interface UsageAnalytics {
  summary: DetailedUsageSummary;
  daily: { date: string; aiActions: number; workflowRuns: number; fileOperations: number }[];
  byOperation: { operation: string; aiActions: number }[];
}

export interface InvoiceSummary {
  id: string;
  amount: number;
  currency: string;
  status: string;
  description: string | null;
  issuedAt: string | null;
  periodStart: string | null;
  periodEnd: string | null;
}

async function parseOrThrow<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error((data as { error?: string }).error || 'Request failed.');
  }
  return data as T;
}

export async function getPlans(): Promise<{ plans: PlanSummary[]; stripe_enabled: boolean }> {
  const res = await fetch('/api/billing/plans', { cache: 'no-store' });
  return parseOrThrow(res);
}

export async function getSubscription(): Promise<{ subscription: SubscriptionSummary; usage: UsageSummary }> {
  const res = await fetch('/api/billing/subscription', { cache: 'no-store' });
  return parseOrThrow(res);
}

export async function getUsageAnalytics(): Promise<UsageAnalytics> {
  const res = await fetch('/api/billing/usage', { cache: 'no-store' });
  return parseOrThrow(res);
}

export async function getInvoices(): Promise<{ invoices: InvoiceSummary[] }> {
  const res = await fetch('/api/billing/invoices', { cache: 'no-store' });
  return parseOrThrow(res);
}

export async function startCheckout(
  planTier: string,
  billingCycle: 'monthly' | 'annual'
): Promise<{ checkout_url: string | null; dev_mode: boolean; subscription?: SubscriptionSummary }> {
  const res = await fetch('/api/billing/checkout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ planTier, billingCycle }),
  });
  return parseOrThrow(res);
}

export async function cancelSubscription(immediately = false): Promise<{ subscription: SubscriptionSummary }> {
  const res = await fetch('/api/billing/cancel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ immediately }),
  });
  return parseOrThrow(res);
}
