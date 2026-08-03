import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const { id } = await params;
  const body = await req.json().catch(() => ({}));
  const result = await backendFetch(`/task/${id}/resume`, {
    method: 'POST',
    token,
    body: { correction: body.correction ?? null },
  });
  if (!result.ok) {
    return NextResponse.json({ error: 'Could not resume the task.' }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
