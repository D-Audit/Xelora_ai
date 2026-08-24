import { NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const { id } = await params;
  const result = await backendFetch(`/files/${id}/reprocess`, { method: 'POST', token });
  if (!result.ok) {
    const detail = result.data as { detail?: string; error?: string };
    return NextResponse.json({ error: detail.detail || detail.error || 'Could not reprocess file.' }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
