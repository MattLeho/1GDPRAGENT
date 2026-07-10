import { NextResponse } from 'next/server';
import { getEngineHealth } from '@/lib/execution/router';

export async function GET(_request:Request,{params}:{params:Promise<{engineId:string}>}){
    const {engineId}=await params; return NextResponse.json(await getEngineHealth(engineId));
}
