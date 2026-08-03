import { NextResponse, NextRequest } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { getProcessingSettings, saveProcessingSettings } from '@/lib/execution/router';

export async function GET(request: NextRequest){
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;return NextResponse.json(await getProcessingSettings());}
export async function POST(request: NextRequest){
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try{return NextResponse.json({success:true,settings:await saveProcessingSettings(await request.json())});}
    catch(error){return NextResponse.json({success:false,message:error instanceof Error?error.message:String(error)},{status:400});}
}
