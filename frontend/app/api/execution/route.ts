import { NextResponse, NextRequest } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { executeTask } from '@/lib/execution/router';

export async function POST(request: NextRequest){
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    const invocation=await request.json();
    const result=await executeTask({...invocation,profileId:authority.profileId});
    return NextResponse.json(result,{status:result.ok?200:result.error.code==='PRIVACY_POLICY_BLOCK'?403:422});
}
