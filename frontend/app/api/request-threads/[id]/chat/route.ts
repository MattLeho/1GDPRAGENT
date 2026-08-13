import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { getRLMAgent, ChatMessage } from '@/lib/rlm-agent';
import { RequestService } from '@/lib/requests/service';

const requests = new RequestService();

// Get chat history for a request
export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const { id } = await params;

        if (!await requests.get(authority.profileId, id)) {
            return NextResponse.json({ success: false, error: 'Request not found' }, { status: 404 });
        }
        const history = await requests.chat(authority.profileId, id);

        return NextResponse.json({
            success: true,
            messages: history.map(row => ({ id: row.id, role: row.sender, content: row.message, timestamp: row.timestamp })),
        });
    } catch (error) {
        console.error('Error fetching chat messages:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to fetch chat messages', messages: [] },
            { status: 500 }
        );
    }
}

// Send message to RLM Agent — tool-calling GDPR assistant with hybrid RAG
export async function POST(
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const { id } = await params;
        const body = await request.json();
        const { message } = body;

        if (!message || typeof message !== 'string') {
            return NextResponse.json(
                { success: false, error: 'Message is required' },
                { status: 400 }
            );
        }

        if (!await requests.get(authority.profileId, id)) {
            return NextResponse.json(
                { success: false, error: 'Request not found' },
                { status: 404 }
            );
        }

        // Get chat history for conversation context
        const historyResult = (await requests.chat(authority.profileId, id)).slice(-20);

        // Map DB rows to ChatMessage format for the agent
        const conversationHistory: ChatMessage[] = historyResult.map((row) => ({
            role: row.sender === 'user' ? 'user' as const : 'assistant' as const,
            content: row.message,
        }));

        // Call RLM Agent — it handles tool execution, knowledge graph search,
        // document retrieval, GDPR references, and recursive decomposition internally
        const agent = getRLMAgent();
        const rlmResponse = await agent.chat(authority.profileId, id, message, conversationHistory);

        console.log(`[Chat] RLM Agent responded: ${rlmResponse.iterations} iteration(s), tools: [${rlmResponse.toolsUsed.join(', ')}]`);

        // Store user message and AI response in database
        await requests.appendChatMessage(authority.profileId, id, 'user', message);
        await requests.appendChatMessage(authority.profileId, id, 'assistant', rlmResponse.content);

        return NextResponse.json({
            success: true,
            response: rlmResponse.content,
            toolsUsed: rlmResponse.toolsUsed,
            iterations: rlmResponse.iterations,
        });
    } catch (error) {
        console.error('Error processing chat message:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to process message', details: String(error) },
            { status: 500 }
        );
    }
}
