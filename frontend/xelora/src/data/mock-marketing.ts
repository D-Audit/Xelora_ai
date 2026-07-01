import type { DesktopRelease, NotificationCategory } from '@/types';

export interface FeatureDetail {
  title: string;
  summary: string;
  whoBenefits: string;
  useCase: string;
  surface: 'web dashboard' | 'desktop app' | 'both';
}

export const marketingFeatures: FeatureDetail[] = [
  {
    title: 'AI assistant',
    summary: 'Talk to Xelora in plain English and turn spreadsheet tasks into guided workflows.',
    whoBenefits: 'Non-technical users, analysts, and operations teams',
    useCase: 'Ask Xelora to clean a monthly export and generate a summary sheet.',
    surface: 'both',
  },
  {
    title: 'Workflow planning',
    summary: 'Xelora breaks a request into visible steps so you can review each action.',
    whoBenefits: 'Teams that need predictable, reversible changes',
    useCase: 'Plan a payroll cleanup workflow before it touches the live workbook.',
    surface: 'web dashboard',
  },
  {
    title: 'Data cleaning',
    summary: 'Standardise casing, trim whitespace, remove duplicates, and flag exceptions.',
    whoBenefits: 'Accountants, researchers, and data teams',
    useCase: 'Prepare an inconsistent customer export for reporting.',
    surface: 'desktop app',
  },
  {
    title: 'Formula assistance',
    summary: 'Generate formulas and plain-English explanations side by side.',
    whoBenefits: 'Finance teams, students, and spreadsheet-heavy operators',
    useCase: 'Build a SUMIFS formula for regional revenue analysis.',
    surface: 'both',
  },
  {
    title: 'Reporting',
    summary: 'Create summary sheets and polished outputs with consistent formatting.',
    whoBenefits: 'Managers and teams producing recurring reports',
    useCase: 'Automate the monthly KPI deck export from a workbook.',
    surface: 'desktop app',
  },
  {
    title: 'Charts',
    summary: 'Generate restrained, readable charts from cleaned data.',
    whoBenefits: 'Analysts and reviewers who need a quick visual summary',
    useCase: 'Add a regional revenue chart to the final workbook.',
    surface: 'both',
  },
  {
    title: 'Batch processing',
    summary: 'Run one workflow across many files without rebuilding the steps.',
    whoBenefits: 'Operations and inventory teams',
    useCase: 'Process 40 regional spreadsheets with the same quality checks.',
    surface: 'desktop app',
  },
  {
    title: 'Version history',
    summary: 'Every automation run is reversible with clear checkpoints.',
    whoBenefits: 'Anyone who needs safe editing and auditability',
    useCase: 'Return to the previous version if a formula change was too aggressive.',
    surface: 'both',
  },
  {
    title: 'Local and cloud file options',
    summary: 'Choose local-only processing or opt into Xelora Cloud when it helps.',
    whoBenefits: 'Privacy-conscious users and distributed teams',
    useCase: 'Keep sensitive files local while using cloud sync for approved reports.',
    surface: 'both',
  },
  {
    title: 'Approval controls',
    summary: 'Pause automation at key points and wait for human approval.',
    whoBenefits: 'Businesses with review policies',
    useCase: 'Approve the creation of a new summary sheet before export.',
    surface: 'web dashboard',
  },
  {
    title: 'Team collaboration',
    summary: 'Invite teammates, assign roles, and share approved workflows.',
    whoBenefits: 'Small businesses and growing teams',
    useCase: 'Let an operator run workflows while an administrator manages access.',
    surface: 'web dashboard',
  },
  {
    title: 'Device management',
    summary: 'See which computers are authorised and revoke access when needed.',
    whoBenefits: 'Team owners and admins',
    useCase: 'Make the office laptop primary and remove an old home device.',
    surface: 'web dashboard',
  },
];

export interface SolutionDetail {
  title: string;
  description: string;
  focus: string[];
  outcome: string;
}

export const marketingSolutions: SolutionDetail[] = [
  {
    title: 'Accounting and finance',
    description: 'Clean exports, create reconciliation sheets, and generate monthly reporting packs.',
    focus: ['Account reconciliations', 'Payroll checks', 'Revenue reporting'],
    outcome: 'Reduce repetitive month-end spreadsheet work.',
  },
  {
    title: 'Sales operations',
    description: 'Standardise lead and pipeline exports before reports and dashboards are built.',
    focus: ['Pipeline cleaning', 'Regional reports', 'Batch file processing'],
    outcome: 'Move from raw exports to decision-ready summaries faster.',
  },
  {
    title: 'Human resources',
    description: 'Review employee sheets, detect anomalies, and prepare controlled reports.',
    focus: ['Headcount lists', 'Payroll tables', 'Onboarding records'],
    outcome: 'Keep HR spreadsheets tidy and reviewable.',
  },
  {
    title: 'Inventory management',
    description: 'Flag low stock, calculate reorder quantities, and prepare supplier exports.',
    focus: ['Threshold checks', 'Stock normalisation', 'Reorder lists'],
    outcome: 'Turn inventory spreadsheets into practical action lists.',
  },
  {
    title: 'Data analysis',
    description: 'Prepare data for analysis, generate formulas, and produce charts with context.',
    focus: ['Cleaning', 'Formula generation', 'Visual summaries'],
    outcome: 'Spend more time interpreting data and less time preparing it.',
  },
  {
    title: 'Education and research',
    description: 'Process survey sheets, tidy responses, and build reliable summary tables.',
    focus: ['Survey cleaning', 'Grade exports', 'Research tables'],
    outcome: 'Keep academic spreadsheets consistent and trustworthy.',
  },
  {
    title: 'Small-business administration',
    description: 'Automate recurring admin sheets without needing a dedicated analyst.',
    focus: ['Invoices', 'Scheduling', 'Operations tracking'],
    outcome: 'Run lightweight back-office work with fewer manual steps.',
  },
];

export interface ResourceItem {
  title: string;
  category: string;
  description: string;
  audience: string;
}

export const resourceItems: ResourceItem[] = [
  {
    title: 'Getting started guide',
    category: 'Help centre',
    description: 'Set up Xelora, sign in, and understand how the web and desktop apps work together.',
    audience: 'New users',
  },
  {
    title: 'Workflow design tips',
    category: 'Workflow guides',
    description: 'Plan reusable automations with approval points and error handling.',
    audience: 'Operators and admins',
  },
  {
    title: 'Spreadsheet cleanup checklist',
    category: 'Tutorials',
    description: 'A practical checklist for cleaning imports before reporting.',
    audience: 'Analysts and accountants',
  },
  {
    title: 'Formula patterns for reporting',
    category: 'Spreadsheet tips',
    description: 'Common formula shapes for totals, lookups, and conditional logic.',
    audience: 'Students and teams',
  },
  {
    title: 'Product release notes',
    category: 'Product updates',
    description: 'Track improvements to the web dashboard and desktop app mock releases.',
    audience: 'Everyone',
  },
  {
    title: 'Template gallery',
    category: 'Templates',
    description: 'Browse starter workflows for accounting, reporting, payroll, and analysis.',
    audience: 'Teams',
  },
];

export interface SecurityTopic {
  title: string;
  summary: string;
  details: string[];
}

export const securityTopics: SecurityTopic[] = [
  {
    title: 'Local processing',
    summary: 'Run on-device by default.',
    details: ['Keep files on your computer when a workflow can be completed locally.', 'Use the desktop app to monitor progress and approve changes.'],
  },
  {
    title: 'Temporary cloud processing',
    summary: 'Use cloud compute only when you choose.',
    details: ['Cloud processing is opt-in per file or workflow.', 'Processing sessions are short-lived and tied to your account.'],
  },
  {
    title: 'Storage controls',
    summary: 'Control what is stored and for how long.',
    details: ['Set retention limits from settings.', 'Delete files and session data when they are no longer needed.'],
  },
  {
    title: 'File ownership',
    summary: 'Your files remain your files.',
    details: ['Xelora does not claim ownership of your workbook content.', 'Shared workspaces still keep ownership and permissions visible.'],
  },
  {
    title: 'AI transparency',
    summary: 'See what the AI reads and why.',
    details: ['Preview the fields and sheets used for a suggestion.', 'Approve or edit any workflow step before it runs.'],
  },
  {
    title: 'Session security',
    summary: 'Use sign-in controls and device authorisation.',
    details: ['Review active devices from the dashboard.', 'Remove access from devices you no longer use.'],
  },
];

export const downloadReleases: DesktopRelease[] = [
  {
    id: 'release-130',
    version: '1.3.0',
    os: 'windows',
    status: 'stable',
    releasedAt: '2026-07-20T00:00:00Z',
    fileSizeMB: 84,
    downloadCount: 18420,
    releaseNotes: [
      'Improved workflow step previews',
      'Faster batch processing on large files',
      'Fixed formula rendering in review mode',
    ],
    downloadUrl: '/api/download/windows',
    checksum: 'SHA-256: 7E2F-9C8A-4F31-2E90-4B4C-91F2-8C91-2AB3',
  },
  {
    id: 'release-130-macos',
    version: '1.3.0',
    os: 'macos',
    status: 'coming_soon',
    releasedAt: '2026-07-20T00:00:00Z',
    fileSizeMB: 86,
    downloadCount: 0,
    releaseNotes: ['Mac build is in progress.'],
  },
  {
    id: 'release-130-linux',
    version: '1.3.0',
    os: 'linux',
    status: 'coming_soon',
    releasedAt: '2026-07-20T00:00:00Z',
    fileSizeMB: 88,
    downloadCount: 0,
    releaseNotes: ['Linux build is in progress.'],
  },
];

export const publicFaqs = [
  {
    question: 'Does Xelora replace Excel?',
    answer: 'No. Xelora works alongside Excel and other spreadsheet tools. It automates repetitive work while you keep using the files and formats you already know.',
  },
  {
    question: 'Do I need the desktop app?',
    answer: 'The web app manages your account, workflows, and files. The desktop app runs spreadsheet automations locally and gives you the in-file review experience.',
  },
  {
    question: 'Can Xelora work offline?',
    answer: 'Yes. Local workflows can run offline in Xelora Desktop. The web dashboard itself needs a connection.',
  },
  {
    question: 'What happens when my plan expires?',
    answer: 'Your account becomes read-only, but files and workflows are preserved. You can upgrade to keep running automations.',
  },
  {
    question: 'Are my spreadsheet files uploaded automatically?',
    answer: 'No. Uploads are always user-controlled. Local processing is the default, and cloud processing must be explicitly enabled.',
  },
  {
    question: 'Can I edit while an automation is running?',
    answer: 'Yes. You can pause a run, make changes, and continue. Xelora re-checks the workbook before it proceeds.',
  },
  {
    question: 'Which spreadsheet formats are supported?',
    answer: 'Xelora supports .xlsx, .xls, .csv, .ods, and .tsv files.',
  },
];

export const howItWorksJourney = [
  'Create an account',
  'Choose a subscription',
  'Download Xelora Desktop',
  'Sign in using the same account',
  'Open a spreadsheet',
  'Describe the work',
  'Review the AI-generated steps',
  'Run the workflow',
  'Edit or approve changes',
  'Save locally or to the cloud',
];

export const billingFeatureNotes = [
  'AI actions',
  'Workflow runs',
  'File operations',
  'Storage',
  'Devices',
  'Team seats',
  'Usage-reset date',
];

export const notificationCategories: NotificationCategory[] = [
  'workflow',
  'billing',
  'account',
  'team',
  'product',
];
