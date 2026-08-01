import { NextResponse } from 'next/server';
import { getSessionToken } from '@/lib/session';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || '';

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const { id } = await params;
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  if (BACKEND_API_KEY) headers['X-API-Key'] = BACKEND_API_KEY;

  const res = await fetch(`${BACKEND_URL}/files/${id}/download`, { headers, cache: 'no-store' });
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
