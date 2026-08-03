import { NextResponse, NextRequest } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { getEngineHealth } from '@/lib/execution/router';

export async function GET(_request: NextRequest,{params}:{params:Promise<{engineId:string}>}){
    const authority = await requireApiSession(_request);
    if (authority instanceof NextResponse) return authority;
    const {engineId}=await params; return NextResponse.json(await getEngineHealth(engineId,authority.profileId));
}
