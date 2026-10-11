import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const { id } = await params;
  const result = await backendFetch(`/workflows/${id}`, { token });
  if (!result.ok) {
    return NextResponse.json({ error: 'Workflow not found.' }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}

export async function PATCH(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const { id } = await params;
  const body = await req.json();
  const result = await backendFetch(`/workflows/${id}`, {
    method: 'PATCH',
    token,
    body: { name: body.name, description: body.description ?? '', steps: body.steps ?? [], tags: body.tags ?? [], isPublic: false },
  });
  if (!result.ok) {
    return NextResponse.json({ error: 'Could not update workflow.' }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}

export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const { id } = await params;
  const result = await backendFetch(`/workflows/${id}`, { method: 'DELETE', token });
  if (!result.ok) {
    return NextResponse.json({ error: 'Could not delete workflow.' }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
