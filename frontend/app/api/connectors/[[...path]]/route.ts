import { NextRequest, NextResponse } from 'next/server';

const baseUrl=()=>process.env.INTELLIGENCE_SERVICE_URL||process.env.INTELLIGENCE_URL||'http://intelligence:8000';
async function proxy(request:NextRequest,context:{params:Promise<{path?:string[]}>}){
  const {path=[]}=await context.params;
  const suffix=path.map(encodeURIComponent).join('/');
  const url=`${baseUrl()}/connectors${suffix?`/${suffix}`:''}${request.nextUrl.search}`;
  try{
    const body=['GET','HEAD'].includes(request.method)?undefined:await request.text();
    const response=await fetch(url,{method:request.method,body:body||undefined,headers:{'content-type':request.headers.get('content-type')||'application/json'},cache:'no-store',signal:AbortSignal.timeout(120_000)});
    const payload=await response.json().catch(()=>({detail:`Connector service returned ${response.status}`}));
    return NextResponse.json(payload,{status:response.status});
  }catch(error){return NextResponse.json({detail:'Connector service is unavailable',error:error instanceof Error?error.message:String(error)},{status:503})}
}
export const GET=proxy;export const POST=proxy;export const PUT=proxy;export const DELETE=proxy;
