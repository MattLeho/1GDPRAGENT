import { NextResponse, NextRequest } from 'next/server';
import { intelligenceAuthorityHeaders, requireApiSession } from '@/lib/api-session';

const intelligenceUrl = process.env.INTELLIGENCE_URL || 'http://localhost:8001'

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
  const body = await request.json()
  const subjectRef = String(body?.personaName || body?.name || 'local-subject')
  const candidates = [
    ...(Array.isArray(body?.emails) ? body.emails.map((label: string) => ({ type: 'Identifier', label, properties: { controller: 'manual', identifier_type: 'email' }, subject_ref: subjectRef })) : []),
    ...(Array.isArray(body?.phones) ? body.phones.map((label: string) => ({ type: 'Identifier', label, properties: { controller: 'manual', identifier_type: 'phone' }, subject_ref: subjectRef })) : []),
    ...(Array.isArray(body?.accounts) ? body.accounts.map((account: Record<string, unknown>) => ({ type: 'Account', label: String(account.username || account.platform || 'account'), properties: { controller: String(account.platform || 'manual') }, subject_ref: subjectRef })) : []),
  ]
  if (!candidates.length) candidates.push({ type: 'Subject', label: subjectRef, properties: { controller: 'manual' }, subject_ref: subjectRef })
  const results = []
  const target = `${intelligenceUrl}/evidence/manual-node`
  for (const candidate of candidates) {
    const body=JSON.stringify(candidate)
    const response = await fetch(target, { method: 'POST', headers: intelligenceAuthorityHeaders(authority.profileId, target, 'POST','application/json',undefined,undefined,body), body, cache: 'no-store' })
    results.push(await response.json())
  }
  return NextResponse.json({ success: true, results })
}
