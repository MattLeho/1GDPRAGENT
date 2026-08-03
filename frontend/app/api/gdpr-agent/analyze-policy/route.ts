import { NextRequest,NextResponse } from 'next/server';
import { executeTask } from '@/lib/execution/router';
import { intelligenceAuthorityHeaders, requireApiSession } from '@/lib/api-session';

export async function POST(request:NextRequest){
    try{
        const authority=await requireApiSession(request);if(authority instanceof NextResponse)return authority;
        const{url,company}=await request.json();if(!url)return NextResponse.json({success:false,error:'URL is required'},{status:400});
        const response=await fetch(url,{headers:{'User-Agent':'GDPR-Agent/2.0 privacy-policy acquisition'},signal:AbortSignal.timeout(30_000)});
        if(!response.ok)throw new Error(`Policy acquisition returned ${response.status}`);
        const html=await response.text();const policyText=html.replace(/<script[\s\S]*?<\/script>/gi,' ').replace(/<style[\s\S]*?<\/style>/gi,' ').replace(/<[^>]+>/g,' ').replace(/&nbsp;/g,' ').replace(/&amp;/g,'&').replace(/\s+/g,' ').trim().slice(0,100_000);
        const result=await executeTask({taskKey:'policy.interpretation',workflowKey:'policy.analysis',input:{text:`Controller: ${company||new URL(url).hostname}\nPolicy URL: ${url}\n\n${policyText}`},configuration:{systemPrompt:'Analyse this UK privacy policy using only supplied text. Return strict JSON with markdown_content, summary, compliance_score (0-100), data_collected array, dpo_email string or null, legal_basis, retention_period, third_party_sharing, user_rights array, and claims array. Each claims item must contain claim_type and exact_quote copied byte-for-byte from the supplied policy text. Omit any claim without an exact quote. Cite relevant UK GDPR provisions in the markdown. Do not infer absent facts.'},profileId:authority.profileId});
        if(!result.ok)return NextResponse.json({success:false,error:result.error.message,executionRecordId:result.executionRecordId},{status:422});
        const text=(result.output as {text?:unknown}).text;if(typeof text!=='string')throw new Error('Policy engine returned no text');
        const match=text.match(/\{[\s\S]*\}/);if(!match)throw new Error('Policy engine did not return structured JSON');const analysis=JSON.parse(match[0]);
        const claims=(Array.isArray(analysis.claims)?analysis.claims:[]).flatMap((item:{claim_type?:unknown;exact_quote?:unknown})=>{
            if(typeof item.claim_type!=='string'||typeof item.exact_quote!=='string')return[];
            const start=policyText.indexOf(item.exact_quote);if(start<0)return[];
            return[{claim_type:item.claim_type,exact_quote:item.exact_quote,byte_start:Buffer.byteLength(policyText.slice(0,start),'utf8'),byte_end:Buffer.byteLength(policyText.slice(0,start+item.exact_quote.length),'utf8')}];
        });
        const baseUrl=process.env.INTELLIGENCE_SERVICE_URL||process.env.INTELLIGENCE_URL||'http://intelligence:8000';
        const acquiredAt=new Date();
        const sourceUrl=`${baseUrl}/extract/policy-claims`;
        const sourceBody=JSON.stringify({content:policyText,policy_key:new URL(url).hostname,version_label:acquiredAt.toISOString(),retrieved_at:acquiredAt.toISOString(),authorisation_basis:'User-initiated acquisition of a publicly presented privacy policy',source_uri:url,controller_key:company||new URL(url).hostname,claims});
        const sourceResponse=await fetch(sourceUrl,{method:'POST',headers:intelligenceAuthorityHeaders(authority.profileId,sourceUrl,'POST','application/json',undefined,undefined,sourceBody),body:sourceBody,signal:AbortSignal.timeout(120_000)});
        const provenance=await sourceResponse.json();if(!sourceResponse.ok)throw new Error(provenance.detail||'Canonical policy ingestion failed');
        return NextResponse.json({success:true,markdownContent:analysis.markdown_content||policyText,summary:analysis.summary,analysis:{complianceScore:analysis.compliance_score,dataCollected:analysis.data_collected||[],dpoEmail:analysis.dpo_email,legalBasis:analysis.legal_basis,retentionPeriod:analysis.retention_period,thirdPartySharing:analysis.third_party_sharing,userRights:analysis.user_rights||[]},executionRecordId:result.executionRecordId,provenance});
    }catch(error){return NextResponse.json({success:false,error:error instanceof Error?error.message:String(error)},{status:500});}
}
