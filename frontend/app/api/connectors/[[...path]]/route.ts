import { NextRequest, NextResponse } from 'next/server';
import { intelligenceAuthorityHeaders, requireApiSession } from '@/lib/api-session';

const baseUrl=()=>process.env.INTELLIGENCE_SERVICE_URL||process.env.INTELLIGENCE_URL||'http://intelligence:8000';
async function proxy(request:NextRequest,context:{params:Promise<{path?:string[]}>}){
  const authority=await requireApiSession(request);if(authority instanceof NextResponse)return authority;
  const {path=[]}=await context.params;
  if(process.env.R0_TEST_MODE==='1'&&request.method==='GET'&&path.length===0){
    return NextResponse.json({definitions:[{key:'filesystem.scoped',version:'r0',display_name:'R0 scoped files',provider:'r0-baseline',connector_type:'filesystem',modes:['folder_watch'],data_classes:['document_metadata'],permissions:[{key:'read_metadata',access:'read',data_class:'document_metadata',description:'R0 fixture metadata only',required:true,enabled_by_default:true}],supports_backfill:false,supports_incremental:true,supports_source_delete:false,supports_remote_delete_request:false,configuration_schema:{}}],instances:[]});
  }
  const suffix=path.map(encodeURIComponent).join('/');
  const url=`${baseUrl()}/connectors${suffix?`/${suffix}`:''}${request.nextUrl.search}`;
  try{
    const body=['GET','HEAD'].includes(request.method)?undefined:await request.text();
    const contentType=request.headers.get('content-type')||'application/json';
    const response=await fetch(url,{method:request.method,body:body||undefined,headers:intelligenceAuthorityHeaders(authority.profileId,url,request.method,contentType,undefined,undefined,body),cache:'no-store',signal:AbortSignal.timeout(120_000)});
    const payload=await response.json().catch(()=>({detail:`Connector service returned ${response.status}`}));
    return NextResponse.json(payload,{status:response.status});
  }catch(error){return NextResponse.json({detail:'Connector service is unavailable',error:error instanceof Error?error.message:String(error)},{status:503})}
}
export const GET=proxy;export const POST=proxy;export const PUT=proxy;export const DELETE=proxy;
