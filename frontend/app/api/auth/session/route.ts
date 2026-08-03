import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';

export async function GET(request: NextRequest) {
  const authority = await requireApiSession(request);
  if (authority instanceof NextResponse) return authority;
  return NextResponse.json({ authenticated: true, expiresAt: authority.expiresAt });
}
