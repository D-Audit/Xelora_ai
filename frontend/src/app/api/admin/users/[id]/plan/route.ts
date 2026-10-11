import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const { id } = await params;
  const body = await req.json();
  const result = await backendFetch(`/admin/users/${id}/plan`, {
    method: 'POST',
    token,
    body: { plan_tier: body.planTier },
  });
  if (!result.ok) {
    const detail = (result.data as { detail?: string })?.detail || 'Could not update plan.';
    return NextResponse.json({ error: detail }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
