import { NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string; versionId: string }> }) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const { id, versionId } = await params;
  const result = await backendFetch(`/files/${id}/versions/${versionId}`, { method: 'DELETE', token });
  if (!result.ok) {
    const detail = result.data as { detail?: string; error?: string };
    return NextResponse.json({ error: detail.detail || detail.error || 'Could not delete the version.' }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
