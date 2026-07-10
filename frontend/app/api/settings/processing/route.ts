import { NextResponse } from 'next/server';
import { getProcessingSettings, saveProcessingSettings } from '@/lib/execution/router';

export async function GET(){return NextResponse.json(await getProcessingSettings());}
export async function POST(request:Request){
    try{return NextResponse.json({success:true,settings:await saveProcessingSettings(await request.json())});}
    catch(error){return NextResponse.json({success:false,message:error instanceof Error?error.message:String(error)},{status:400});}
}
