import { NextResponse } from 'next/server';
import { executeTask } from '@/lib/execution/router';

export async function POST(request:Request){
    const result=await executeTask(await request.json());
    return NextResponse.json(result,{status:result.ok?200:result.error.code==='PRIVACY_POLICY_BLOCK'?403:422});
}
