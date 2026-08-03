import { NextResponse, NextRequest } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { getModelPreferences, saveModelPreferences } from '@/lib/model-preferences';

interface ModelPreferencesBody {
    workflowBackend?: unknown;
    provider?: unknown;
    model?: unknown;
    workflowModels?: unknown;
}

export async function GET(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    const preferences = await getModelPreferences();
    return NextResponse.json(preferences);
}

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const body: ModelPreferencesBody = await request.json();

        const preferences = await saveModelPreferences({
            workflowBackend: body.workflowBackend,
            provider: body.provider,
            model: body.model,
            workflowModels: body.workflowModels,
        });

        return NextResponse.json({ success: true, preferences });
    } catch (error) {
        console.error('[Model Preferences] Save failed:', error);
        return NextResponse.json(
            { success: false, message: 'Failed to save model preferences' },
            { status: 500 },
        );
    }
}
