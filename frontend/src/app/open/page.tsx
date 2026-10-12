'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { OpenInDesktop } from '@/components/desktop/open-in-desktop';

/** Browser landing page that hands off to Xelora Desktop (see src/proxy.ts). */
export default function OpenPage() {
  return <Suspense fallback={null}><Open /></Suspense>;
}

function Open() {
  const params = useSearchParams();
  return <OpenInDesktop path={params.get('path') ?? '/dashboard/agent'} welcome={params.get('welcome') === '1'} />;
}
