import { NextResponse } from 'next/server';
import { WORKFLOW_DEFINITIONS, getWorkflowPreferences, saveWorkflowPreference, type WorkflowPreference } from '@/lib/workflows/registry';

export async function GET(){return NextResponse.json({definitions:WORKFLOW_DEFINITIONS,preferences:await getWorkflowPreferences()});}
export async function POST(request:Request){
    try{return NextResponse.json({success:true,preference:await saveWorkflowPreference(await request.json() as WorkflowPreference)});}
    catch(error){return NextResponse.json({success:false,message:error instanceof Error?error.message:String(error)},{status:400});}
}
