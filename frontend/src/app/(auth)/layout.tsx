import Link from 'next/link';
import { XeloraLogo } from '@/components/ui/xelora-logo';

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-white">
      <header className="px-6 py-5">
        <Link href="/" aria-label="Xelora home" className="inline-flex">
          <XeloraLogo size="sm" />
        </Link>
      </header>
      <main className="flex flex-1 items-start justify-center px-4 pb-16 pt-8 sm:items-center sm:pt-0">
        <div className="w-full max-w-[400px]">{children}</div>
      </main>
      <footer className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 px-6 py-6 text-xs text-xelora-text-muted">
        <Link href="/terms" className="hover:text-xelora-text">Terms</Link>
        <Link href="/privacy" className="hover:text-xelora-text">Privacy</Link>
        <Link href="/security" className="hover:text-xelora-text">Security</Link>
        <Link href="/contact" className="hover:text-xelora-text">Help</Link>
      </footer>
    </div>
  );
}
