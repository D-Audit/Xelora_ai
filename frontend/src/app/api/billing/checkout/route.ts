import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function POST(req: NextRequest) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const body = await req.json();
  const result = await backendFetch('/billing/checkout', {
    method: 'POST',
    token,
    body: { plan_tier: body.planTier, billing_cycle: body.billingCycle ?? 'monthly' },
  });

  if (!result.ok) {
    const detail = (result.data as { detail?: string })?.detail || 'Checkout failed.';
    return NextResponse.json({ error: detail }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
