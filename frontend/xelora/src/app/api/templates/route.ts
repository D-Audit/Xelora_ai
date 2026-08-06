import { NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';

export async function GET() {
  const result = await backendFetch('/workflows/templates/list');
  if (!result.ok) {
    return NextResponse.json({ error: 'Could not load templates.' }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
