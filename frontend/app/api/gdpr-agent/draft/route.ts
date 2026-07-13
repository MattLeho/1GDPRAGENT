import { NextRequest,NextResponse } from 'next/server';
import { executeTask } from '@/lib/execution/router';

const requestTypes:Record<string,{label:string;article:number}>={access:{label:'Subject Access Request',article:15},erasure:{label:'Erasure Request',article:17},rectification:{label:'Rectification Request',article:16},portability:{label:'Data Portability Request',article:20},objection:{label:'Objection to Processing',article:21}};

export async function POST(request:NextRequest){
    const body=await request.json();const{requestType,company,userQuery,userName,userEmail,policyUrl}=body;
    if(!requestType||!company||!userQuery||!userName||!userEmail)return NextResponse.json({success:false,error:'Missing required fields'},{status:400});
    const kind=requestTypes[requestType]||{label:'GDPR Request',article:15};
    const input=`Controller: ${company}\nPolicy URL: ${policyUrl||'not supplied'}\nData subject: ${userName} <${userEmail}>\nRequest type: ${kind.label} (UK GDPR Article ${kind.article})\nUser instructions: ${userQuery}`;
    const result=await executeTask({taskKey:'request.drafting',workflowKey:'request.drafting',input:{text:input},configuration:{systemPrompt:'Draft a formal UK GDPR request letter using only the supplied facts. Cite the relevant right and Article 12(3) response period, offer proportionate identity verification, and mention the right to complain to the ICO. Do not invent account identifiers. Return only the complete letter body.'}});
    if(!result.ok)return NextResponse.json({success:false,error:result.error.message,executionRecordId:result.executionRecordId},{status:422});
    const text=(result.output as {text?:unknown}).text;
    if(typeof text!=='string'||!text.trim())return NextResponse.json({success:false,error:'Draft engine returned no text'},{status:502});
    return NextResponse.json({success:true,draft:{subject:`${kind.label} – ${userName}`,body:text,articlesCited:[kind.article,12],company,requestType,deadlineDays:30},executionRecordId:result.executionRecordId});
}
