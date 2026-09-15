import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { processThroughBulkPipeline } from '@/lib/ingestion/bulk';
import { RequestService } from '@/lib/requests/service';

const requests = new RequestService();

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const body = await request.json() as { fileId?:string; action?:string };
        if (!body.fileId) return NextResponse.json({ success:false,error:'fileId is required' }, { status:400 });
        const file = await requests.getOwnedReceivedData(authority.profileId, body.fileId);
        if (!file) return NextResponse.json({ success:false,error:'File not found' }, { status:404 });
        await requests.updateReceivedData(authority.profileId, body.fileId, {status:'processing',processingStage:'local_ingestion',processingProgress:5,errorMessage:null});
        const result = await processThroughBulkPipeline(file,body.action,authority.profileId);
        return NextResponse.json({ success:true,fileId:body.fileId,stage:result.specialist_tasks.length?'specialist_tasks':'completed',progress:100,...result });
    } catch (error) {
        return NextResponse.json({ success:false,error:error instanceof Error ? error.message : String(error) }, { status:422 });
    }
}

// The legacy "ingest to graph" action now enters the same evidence pipeline.
// Graph projection occurs only later from reviewed high-value assertions.
export async function PUT(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    return POST(request);
}
