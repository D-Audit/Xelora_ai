import type { Plan } from '@/types';

export const plans: Plan[] = [
  {
    id: 'plan-trial',
    tier: 'trial',
    name: 'Free Trial',
    description: 'Explore Xelora for 14 days with no commitment.',
    monthlyPrice: 0,
    annualPrice: 0,
    limits: {
      aiActionsPerMonth: 30,
      workflowRunsPerMonth: 5,
      maxFileSizeMB: 5,
      savedWorkflows: 2,
      cloudStorageGB: 0,
      devices: 1,
      historyDays: 7,
      teamMembers: 1,
      batchProcessing: false,
      apiAccess: false,
      prioritySupport: false,
      auditHistory: false,
      rolePermissions: false,
      customWorkspace: false,
    },
  },
  {
    id: 'plan-starter',
    tier: 'starter',
    name: 'Starter',
    description: 'For individuals getting started with spreadsheet automation.',
    monthlyPrice: 12,
    annualPrice: 9,
    limits: {
      aiActionsPerMonth: 300,
      workflowRunsPerMonth: 50,
      maxFileSizeMB: 25,
      savedWorkflows: 10,
      cloudStorageGB: 2,
      devices: 2,
      historyDays: 30,
      teamMembers: 1,
      batchProcessing: false,
      apiAccess: false,
      prioritySupport: false,
      auditHistory: false,
      rolePermissions: false,
      customWorkspace: false,
    },
  },
  {
    id: 'plan-professional',
    tier: 'professional',
    name: 'Professional',
    description: 'For analysts and teams who need more power and collaboration.',
    monthlyPrice: 35,
    annualPrice: 28,
    isPopular: true,
    limits: {
      aiActionsPerMonth: 1500,
      workflowRunsPerMonth: 300,
      maxFileSizeMB: 100,
      savedWorkflows: 100,
      cloudStorageGB: 25,
      devices: 5,
      historyDays: 90,
      teamMembers: 5,
      batchProcessing: true,
      apiAccess: true,
      prioritySupport: true,
      auditHistory: false,
      rolePermissions: false,
      customWorkspace: false,
    },
  },
  {
    id: 'plan-business',
    tier: 'business',
    name: 'Business',
    description: 'For organisations that need enterprise-grade control and support.',
    monthlyPrice: null,
    annualPrice: null,
    isCustom: true,
    limits: {
      aiActionsPerMonth: 'custom',
      workflowRunsPerMonth: 'custom',
      maxFileSizeMB: 'custom',
      savedWorkflows: 'custom',
      cloudStorageGB: 'custom',
      devices: 'custom',
      historyDays: 'custom',
      teamMembers: 'custom',
      batchProcessing: true,
      apiAccess: true,
      prioritySupport: true,
      auditHistory: true,
      rolePermissions: true,
      customWorkspace: true,
    },
  },
];

export const getPlanByTier = (tier: string) =>
  plans.find((p) => p.tier === tier) ?? plans[0];

/** Short, human bullet points for a plan card. */
export function planHighlights(plan: Plan): string[] {
  if (plan.tier === 'business') {
    return ['Custom usage limits', 'Team members and devices to fit your organisation', 'Priority support'];
  }
  const limits = plan.limits;
  const count = (value: Plan['limits']['devices']) => (typeof value === 'number' ? value.toLocaleString() : 'Custom');
  return [
    `${count(limits.aiActionsPerMonth)} AI actions per month`,
    `Files up to ${count(limits.maxFileSizeMB)} MB`,
    `${count(limits.devices)} ${limits.devices === 1 ? 'device' : 'devices'}`,
    ...(typeof limits.teamMembers === 'number' && limits.teamMembers > 1 ? [`Up to ${limits.teamMembers} team members`] : []),
    ...(limits.prioritySupport ? ['Priority support'] : []),
  ];
}
