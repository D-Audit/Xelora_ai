/**
 * Public facts about the business, used by the landing page, footer and
 * legal pages. Set the NEXT_PUBLIC_* values in Vercel before launch so the
 * legal pages name the right company, address and jurisdiction.
 */
export const site = {
  name: 'Xelora',
  tagline: 'The AI assistant that works inside Microsoft Excel.',
  description:
    'Describe what you need in plain language. Xelora does the work in Excel on your PC, checks the result, and asks before making big changes.',
  legalName: process.env.NEXT_PUBLIC_LEGAL_NAME || 'Xelora',
  contactEmail: process.env.NEXT_PUBLIC_CONTACT_EMAIL || 'hello@xelora.app',
  privacyEmail: process.env.NEXT_PUBLIC_PRIVACY_EMAIL || process.env.NEXT_PUBLIC_CONTACT_EMAIL || 'hello@xelora.app',
  address: process.env.NEXT_PUBLIC_LEGAL_ADDRESS || '',
  governingLaw: process.env.NEXT_PUBLIC_GOVERNING_LAW || '',
  legalUpdated: 'October 12, 2026',
  trialDays: 14,
} as const;
