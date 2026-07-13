import { NextRequest,NextResponse } from 'next/server';
import { executeTask } from '@/lib/execution/router';

export async function POST(request:NextRequest){
    try{
        const{url,company}=await request.json();if(!url)return NextResponse.json({success:false,error:'URL is required'},{status:400});
        const response=await fetch(url,{headers:{'User-Agent':'GDPR-Agent/2.0 privacy-policy acquisition'},signal:AbortSignal.timeout(30_000)});
        if(!response.ok)throw new Error(`Policy acquisition returned ${response.status}`);
        const html=await response.text();const policyText=html.replace(/<script[\s\S]*?<\/script>/gi,' ').replace(/<style[\s\S]*?<\/style>/gi,' ').replace(/<[^>]+>/g,' ').replace(/&nbsp;/g,' ').replace(/&amp;/g,'&').replace(/\s+/g,' ').trim().slice(0,100_000);
        const result=await executeTask({taskKey:'policy.interpretation',workflowKey:'policy.analysis',input:{text:`Controller: ${company||new URL(url).hostname}\nPolicy URL: ${url}\n\n${policyText}`},configuration:{systemPrompt:'Analyse this UK privacy policy using only supplied text. Return strict JSON with markdown_content, summary, compliance_score (0-100), data_collected array, dpo_email string or null, legal_basis, retention_period, third_party_sharing, and user_rights array. Cite relevant UK GDPR provisions in the markdown. Do not infer absent facts.'}});
        if(!result.ok)return NextResponse.json({success:false,error:result.error.message,executionRecordId:result.executionRecordId},{status:422});
        const text=(result.output as {text?:unknown}).text;if(typeof text!=='string')throw new Error('Policy engine returned no text');
        const match=text.match(/\{[\s\S]*\}/);if(!match)throw new Error('Policy engine did not return structured JSON');const analysis=JSON.parse(match[0]);
        return NextResponse.json({success:true,markdownContent:analysis.markdown_content||policyText,summary:analysis.summary,analysis:{complianceScore:analysis.compliance_score,dataCollected:analysis.data_collected||[],dpoEmail:analysis.dpo_email,legalBasis:analysis.legal_basis,retentionPeriod:analysis.retention_period,thirdPartySharing:analysis.third_party_sharing,userRights:analysis.user_rights||[]},executionRecordId:result.executionRecordId});
    }catch(error){return NextResponse.json({success:false,error:error instanceof Error?error.message:String(error)},{status:500});}
}
