import { NextResponse, NextRequest } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { monitorInboxBuiltIn } from '@/lib/connectors/email';
import { getWorkflowPreference } from '@/lib/workflows/registry';

export async function POST(request: NextRequest){
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    const preference=await getWorkflowPreference('inbox.monitoring');
    if(!preference.enabled||preference.execution_mode==='disabled')return NextResponse.json({success:false,error:'Inbox monitoring is disabled'},{status:409});
    if(preference.execution_mode==='n8n')return NextResponse.json({success:false,error:'This endpoint runs only the built-in monitor'},{status:409});
    try{return NextResponse.json({success:true,...await monitorInboxBuiltIn()});}
    catch(error){return NextResponse.json({success:false,error:error instanceof Error?error.message:String(error)},{status:502});}
}
