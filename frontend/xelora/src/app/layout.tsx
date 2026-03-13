import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Toaster } from 'sonner';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'Xelora - Automate spreadsheets. Stay in control.',
    template: '%s | Xelora',
  },
  description:
    'Xelora helps you clean data, generate formulas, create reports, and automate repetitive spreadsheet workflows while keeping every change visible, editable, and reversible.',
  keywords: ['spreadsheet automation', 'excel automation', 'data cleaning', 'formula generator', 'workflow automation'],
  openGraph: {
    title: 'Xelora - Automate spreadsheets. Stay in control.',
    description: 'AI-powered spreadsheet automation that keeps you in control.',
    type: 'website',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        {children}
        <Toaster position="bottom-right" richColors closeButton />
      </body>
    </html>
  );
}
