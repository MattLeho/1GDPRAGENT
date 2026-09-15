import { NextRequest,NextResponse } from 'next/server';
import { executeTask } from '@/lib/execution/router';
import { intelligenceAuthorityHeaders, requireApiSession } from '@/lib/api-session';
import { assertPublicHttpUrl, PublicUrlValidationError } from '@/lib/security/public-url';
import { savePolicyAnalysis } from '@/lib/actions/policy-analysis';
import { RequestService } from '@/lib/requests/service';

const requests = new RequestService();

export async function POST(request:NextRequest){
    try{
        const authority=await requireApiSession(request);if(authority instanceof NextResponse)return authority;
        const{url,company,requestId}=await request.json();if(!url)return NextResponse.json({success:false,error:'URL is required'},{status:400});
        if(requestId!==undefined&&typeof requestId!=='string')return NextResponse.json({success:false,error:'requestId must be a string'},{status:400});
        if(requestId&& !await requests.get(authority.profileId,requestId))return NextResponse.json({success:false,error:'Request not found'},{status:404});
        const safeUrl=await assertPublicHttpUrl(url);
        const response=await fetch(safeUrl,{headers:{'User-Agent':'GDPR-Agent/2.0 privacy-policy acquisition'},redirect:'manual',signal:AbortSignal.timeout(30_000)});
        if(!response.ok)throw new Error(`Policy acquisition returned ${response.status}`);
        const html=await response.text();const policyText=html.replace(/<script[\s\S]*?<\/script>/gi,' ').replace(/<style[\s\S]*?<\/style>/gi,' ').replace(/<[^>]+>/g,' ').replace(/&nbsp;/g,' ').replace(/&amp;/g,'&').replace(/\s+/g,' ').trim().slice(0,100_000);
        const result=await executeTask({taskKey:'policy.interpretation',workflowKey:'policy.analysis',input:{text:`Controller: ${company||safeUrl.hostname}\nPolicy URL: ${safeUrl.href}\n\n${policyText}`},configuration:{systemPrompt:'Analyse this UK privacy policy using only supplied text. Return strict JSON with markdown_content, summary, compliance_score (0-100), data_collected array, dpo_email string or null, legal_basis, retention_period, third_party_sharing, user_rights array, and claims array. Each claims item must contain claim_type and exact_quote copied byte-for-byte from the supplied policy text. Omit any claim without an exact quote. Cite relevant UK GDPR provisions in the markdown. Do not infer absent facts.'},profileId:authority.profileId});
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
        const sourceBody=JSON.stringify({content:policyText,policy_key:safeUrl.hostname,version_label:acquiredAt.toISOString(),retrieved_at:acquiredAt.toISOString(),authorisation_basis:'User-initiated acquisition of a publicly presented privacy policy',source_uri:safeUrl.href,controller_key:company||safeUrl.hostname,claims});
        const sourceResponse=await fetch(sourceUrl,{method:'POST',headers:intelligenceAuthorityHeaders(authority.profileId,sourceUrl,'POST','application/json',undefined,undefined,sourceBody),body:sourceBody,signal:AbortSignal.timeout(120_000)});
        const provenance=await sourceResponse.json();if(!sourceResponse.ok)throw new Error(provenance.detail||'Canonical policy ingestion failed');
        const transientAnalysis={complianceScore:analysis.compliance_score,dataCollected:analysis.data_collected||[],dpoEmail:analysis.dpo_email,legalBasis:analysis.legal_basis,retentionPeriod:analysis.retention_period,thirdPartySharing:analysis.third_party_sharing,userRights:analysis.user_rights||[]};
        if(!requestId)return NextResponse.json({success:true,markdownContent:analysis.markdown_content||policyText,summary:analysis.summary,analysis:transientAnalysis,executionRecordId:result.executionRecordId,provenance});
        const persisted=await savePolicyAnalysis({requestId,url:safeUrl.href,dpo_email:analysis.dpo_email||null,data_collected:Array.isArray(analysis.data_collected)?analysis.data_collected:[],retention_period:analysis.retention_period||null,third_party_sharing:Array.isArray(analysis.third_party_sharing)?analysis.third_party_sharing:[],summary:analysis.summary||null,risk_score:typeof analysis.compliance_score==='number'?analysis.compliance_score:null,analysis_raw:analysis&&typeof analysis==='object'?analysis:null,provenance:{policy_claims:provenance,source_uri:safeUrl.href,acquired_at:acquiredAt.toISOString()},executionRecordId:result.executionRecordId});
        if(!persisted.success)return NextResponse.json({success:false,error:persisted.error||'Policy analysis was not persisted'},{status:persisted.error==='Request not found'?404:500});
        return NextResponse.json({success:true,markdownContent:analysis.markdown_content||policyText,summary:analysis.summary,analysis:persisted.analysis,executionRecordId:result.executionRecordId,provenance});
    }catch(error){return NextResponse.json({success:false,error:error instanceof Error?error.message:String(error)},{status:error instanceof PublicUrlValidationError?400:500});}
}
