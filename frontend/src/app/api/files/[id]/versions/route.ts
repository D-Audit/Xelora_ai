import { NextRequest, NextResponse } from 'next/server';
import { backendHeaders, backendUrl } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const incomingForm = await req.formData();
  const file = incomingForm.get('upload');
  if (!file) return NextResponse.json({ error: 'No file provided.' }, { status: 400 });

  const { id } = await params;
  const outgoingForm = new FormData();
  outgoingForm.append('upload', file);
  try {
    const response = await fetch(backendUrl(`/files/${id}/versions`), {
      method: 'POST',
      headers: backendHeaders(token),
      body: outgoingForm,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      return NextResponse.json({ error: data.detail || data.error || 'Could not upload the new version.' }, { status: response.status });
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: 'Could not reach the backend.' }, { status: 502 });
  }
}
