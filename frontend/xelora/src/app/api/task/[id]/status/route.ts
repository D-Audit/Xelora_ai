import { NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const { id } = await params;
  const result = await backendFetch(`/task/${id}/status`, { token });
  if (!result.ok) {
    return NextResponse.json({ error: 'Could not load task status.' }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
