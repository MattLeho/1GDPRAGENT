import { NextResponse, NextRequest } from 'next/server';
import { intelligenceAuthorityHeaders, requireApiSession } from '@/lib/api-session';

const intelligenceUrl=process.env.INTELLIGENCE_URL || 'http://localhost:8001'

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
  const body=await request.json()
  const findingIds=Array.isArray(body?.findingIds) ? body.findingIds : []
  if(!findingIds.length || findingIds.length>100) return NextResponse.json({error:'findingIds must contain 1-100 stable UUIDs'},{status:400})
  const target=`${intelligenceUrl}/evidence/onsit-bulk`
  const encodedBody=JSON.stringify({action:body.action,finding_ids:findingIds,payload:body.payload || {}})
  const response=await fetch(target,{method:'POST',headers:intelligenceAuthorityHeaders(authority.profileId,target,'POST','application/json',undefined,undefined,encodedBody),body:encodedBody,cache:'no-store'})
  return NextResponse.json(await response.json(),{status:response.status})
}
