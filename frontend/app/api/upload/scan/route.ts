import { NextResponse, NextRequest } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { processThroughBulkPipeline } from '@/lib/ingestion/bulk';
import { RequestService } from '@/lib/requests/service';

const requests = new RequestService();

/** Process pending uploads through the registry/adapter pipeline only. */
export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    const files = await requests.pendingReceivedData(authority.profileId);
    const results = { scanned:files.length,processed:0,errors:[] as string[] };
    for (const file of files) {
        try {
            await requests.updateReceivedData(authority.profileId,String(file.id),{status:'processing',processingStage:'local_ingestion',processingProgress:5,errorMessage:null});
            await processThroughBulkPipeline(file,undefined,authority.profileId);
            results.processed += 1;
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            results.errors.push(`${file.file_name}: ${message}`);
            await requests.updateReceivedData(authority.profileId,String(file.id),{status:'error',processingStage:'local_ingestion',errorMessage:message.slice(0,500)});
        }
    }
    return NextResponse.json({ success:results.errors.length===0,...results });
}
