import { NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const { id } = await params;
  const result = await backendFetch(`/task/${id}/reveal`, { token });
  if (!result.ok) {
    const detail =
      (result.data as { error?: string })?.error ||
      (result.data as { detail?: string })?.detail ||
      'Could not load workflow reveal.';
    return NextResponse.json({ error: detail }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
