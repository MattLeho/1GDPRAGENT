import { NextResponse } from 'next/server'

const intelligenceUrl=process.env.INTELLIGENCE_URL || 'http://localhost:8001'

export async function POST(request: Request) {
  const body=await request.json()
  const findingIds=Array.isArray(body?.findingIds) ? body.findingIds : []
  if(!findingIds.length || findingIds.length>100) return NextResponse.json({error:'findingIds must contain 1-100 stable UUIDs'},{status:400})
  const response=await fetch(`${intelligenceUrl}/evidence/onsit-bulk`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action:body.action,finding_ids:findingIds,payload:body.payload || {}}),cache:'no-store'})
  return NextResponse.json(await response.json(),{status:response.status})
}
