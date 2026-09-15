import { NextResponse, NextRequest } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { WORKFLOW_DEFINITIONS, getWorkflowPreferences, saveWorkflowPreference, type WorkflowPreference } from '@/lib/workflows/registry';

export async function GET(request: NextRequest){
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;return NextResponse.json({definitions:WORKFLOW_DEFINITIONS,preferences:await getWorkflowPreferences()});}
export async function POST(request: NextRequest){
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try{return NextResponse.json({success:true,preference:await saveWorkflowPreference(await request.json() as WorkflowPreference)});}
    catch(error){return NextResponse.json({success:false,message:error instanceof Error?error.message:String(error)},{status:400});}
}
