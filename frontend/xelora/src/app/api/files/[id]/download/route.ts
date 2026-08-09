import { NextResponse } from 'next/server';
import { getSessionToken } from '@/lib/session';
import { backendHeaders, backendUrl } from '@/lib/backend';

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const { id } = await params;
  let res: Response;
  try {
    res = await fetch(backendUrl(`/files/${id}/download`), { headers: backendHeaders(token), cache: 'no-store' });
  } catch {
    return NextResponse.json({ error: 'Could not reach the backend.' }, { status: 502 });
  }
  if (!res.ok) {
    return NextResponse.json({ error: 'File not found.' }, { status: res.status });
  }

  const blob = await res.blob();
  return new NextResponse(blob, {
    headers: {
      'Content-Type': res.headers.get('content-type') || 'application/octet-stream',
      'Content-Disposition': res.headers.get('content-disposition') || 'attachment',
    },
  });
}
