import { NextResponse } from 'next/server';
import { getModelPreferences, saveModelPreferences } from '@/lib/model-preferences';

interface ModelPreferencesBody {
    workflowBackend?: unknown;
    provider?: unknown;
    model?: unknown;
}

export async function GET() {
    const preferences = await getModelPreferences();
    return NextResponse.json(preferences);
}

export async function POST(request: Request) {
    try {
        const body: ModelPreferencesBody = await request.json();

        const preferences = await saveModelPreferences({
            workflowBackend: body.workflowBackend,
            provider: body.provider,
            model: body.model,
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
