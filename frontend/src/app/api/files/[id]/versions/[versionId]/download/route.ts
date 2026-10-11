import { NextResponse } from 'next/server';
import { backendHeaders, backendUrl } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function GET(_req: Request, { params }: { params: Promise<{ id: string; versionId: string }> }) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const { id, versionId } = await params;
  try {
    const response = await fetch(backendUrl(`/files/${id}/versions/${versionId}/download`), {
      headers: backendHeaders(token),
      cache: 'no-store',
    });
    if (!response.ok) return NextResponse.json({ error: 'File version not found.' }, { status: response.status });
    const blob = await response.blob();
    return new NextResponse(blob, {
      headers: {
        'Content-Type': response.headers.get('content-type') || 'application/octet-stream',
        'Content-Disposition': response.headers.get('content-disposition') || 'attachment',
      },
    });
  } catch {
    return NextResponse.json({ error: 'Could not reach the backend.' }, { status: 502 });
  }
}
