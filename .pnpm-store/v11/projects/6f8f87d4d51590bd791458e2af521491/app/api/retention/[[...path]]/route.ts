import { NextRequest, NextResponse } from 'next/server';
import { intelligenceAuthorityHeaders, requireApiSession } from '@/lib/api-session';

const baseUrl=()=>process.env.INTELLIGENCE_SERVICE_URL||process.env.INTELLIGENCE_URL||'http://intelligence:8000';
async function proxy(request:NextRequest,context:{params:Promise<{path?:string[]}>}){
  const authority=await requireApiSession(request);if(authority instanceof NextResponse)return authority;
  const {path=[]}=await context.params;
  const suffix=path.map(encodeURIComponent).join('/');
  const url=`${baseUrl()}/retention${suffix?`/${suffix}`:''}${request.nextUrl.search}`;
  try{
    const body=['GET','HEAD'].includes(request.method)?undefined:await request.text();
    const response=await fetch(url,{method:request.method,body:body||undefined,headers:intelligenceAuthorityHeaders(authority.profileId,url,request.method,'application/json',undefined,undefined,body),cache:'no-store',signal:AbortSignal.timeout(120_000)});
    const payload=await response.json().catch(()=>({detail:`Retention service returned ${response.status}`}));
    return NextResponse.json(payload,{status:response.status});
  }catch(error){return NextResponse.json({detail:'Retention service is unavailable',error:error instanceof Error?error.message:String(error)},{status:503})}
}
export const GET=proxy;export const POST=proxy;
