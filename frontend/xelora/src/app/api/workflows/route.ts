import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function GET() {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const result = await backendFetch('/workflows', { token });
  if (!result.ok) {
    return NextResponse.json({ error: 'Could not load workflows.' }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}

export async function POST(req: NextRequest) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const body = await req.json();
  const result = await backendFetch('/workflows', {
    method: 'POST',
    token,
    body: { name: body.name, description: body.description ?? '', steps: body.steps ?? [], tags: body.tags ?? [], isPublic: false },
  });
  if (!result.ok) {
    const detail = (result.data as { detail?: string })?.detail || 'Could not create workflow.';
    return NextResponse.json({ error: detail }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
