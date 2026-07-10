import { NextResponse } from 'next/server'

const intelligenceUrl = process.env.INTELLIGENCE_URL || 'http://localhost:8001'

export async function POST(request: Request) {
  const body = await request.json()
  const subjectRef = String(body?.personaName || body?.name || 'local-subject')
  const candidates = [
    ...(Array.isArray(body?.emails) ? body.emails.map((label: string) => ({ type: 'Identifier', label, properties: { controller: 'manual', identifier_type: 'email' }, subject_ref: subjectRef })) : []),
    ...(Array.isArray(body?.phones) ? body.phones.map((label: string) => ({ type: 'Identifier', label, properties: { controller: 'manual', identifier_type: 'phone' }, subject_ref: subjectRef })) : []),
    ...(Array.isArray(body?.accounts) ? body.accounts.map((account: Record<string, unknown>) => ({ type: 'Account', label: String(account.username || account.platform || 'account'), properties: { controller: String(account.platform || 'manual') }, subject_ref: subjectRef })) : []),
  ]
  if (!candidates.length) candidates.push({ type: 'Subject', label: subjectRef, properties: { controller: 'manual' }, subject_ref: subjectRef })
  const results = []
  for (const candidate of candidates) {
    const response = await fetch(`${intelligenceUrl}/evidence/manual-node`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(candidate), cache: 'no-store' })
    results.push(await response.json())
  }
  return NextResponse.json({ success: true, results })
}
