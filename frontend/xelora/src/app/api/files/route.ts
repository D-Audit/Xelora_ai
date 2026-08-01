import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || '';

export async function GET() {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const result = await backendFetch('/files', { token });
  if (!result.ok) {
    return NextResponse.json({ error: 'Could not load files.' }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}

export async function POST(req: NextRequest) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  // Multipart body - forwarded as-is, not through the JSON backendFetch
  // helper, so the file bytes aren't touched.
  const incomingForm = await req.formData();
  const file = incomingForm.get('upload');
  if (!file) {
    return NextResponse.json({ error: 'No file provided.' }, { status: 400 });
  }

  const outgoingForm = new FormData();
  outgoingForm.append('upload', file);

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  if (BACKEND_API_KEY) headers['X-API-Key'] = BACKEND_API_KEY;

  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/files`, { method: 'POST', headers, body: outgoingForm });
  } catch {
    return NextResponse.json({ error: 'Could not reach the backend.' }, { status: 502 });
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return NextResponse.json({ error: data.detail || data.error || 'Upload failed.' }, { status: res.status });
  }
  return NextResponse.json(data);
}
