import { NextResponse } from 'next/server';
import { ENGINE_DEFINITIONS, TASK_DEFINITIONS, validateRegistry } from '@/lib/execution/registry';
import { getTaskRoutes, saveTaskRoute, type TaskRoute } from '@/lib/execution/router';

export async function GET() {
    const errors=validateRegistry();
    if(errors.length) return NextResponse.json({success:false,errors},{status:500});
    return NextResponse.json({tasks:TASK_DEFINITIONS,engines:ENGINE_DEFINITIONS,routes:await getTaskRoutes()});
}

export async function POST(request:Request) {
    try { return NextResponse.json({success:true,route:await saveTaskRoute(await request.json() as TaskRoute)}); }
    catch(error){ return NextResponse.json({success:false,message:error instanceof Error?error.message:String(error)},{status:400}); }
}
