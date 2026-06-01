import { NextRequest, NextResponse } from 'next/server';
import { pool } from '@/lib/db';
import { getRLMAgent, ChatMessage } from '@/lib/rlm-agent';

// Get chat history for a request
export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    try {
        const { id } = await params;

        // Fetch chat messages from database (actual columns: sender, message)
        const result = await pool.query(
            `SELECT id, sender as role, message as content, timestamp 
             FROM request_chat_messages 
             WHERE request_id = $1 
             ORDER BY timestamp ASC`,
            [id]
        );

        return NextResponse.json({
            success: true,
            messages: result.rows,
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

        // Verify request exists
        const requestResult = await pool.query(
            `SELECT id FROM access_requests WHERE id = $1`,
            [id]
        );

        if (requestResult.rows.length === 0) {
            return NextResponse.json(
                { success: false, error: 'Request not found' },
                { status: 404 }
            );
        }

        // Get chat history for conversation context
        const historyResult = await pool.query(
            `SELECT sender as role, message as content 
             FROM request_chat_messages 
             WHERE request_id = $1 
             ORDER BY timestamp ASC 
             LIMIT 20`,
            [id]
        );

        // Map DB rows to ChatMessage format for the agent
        const conversationHistory: ChatMessage[] = historyResult.rows.map((row: any) => ({
            role: row.role === 'user' ? 'user' as const : 'assistant' as const,
            content: row.content,
        }));

        // Call RLM Agent — it handles tool execution, knowledge graph search,
        // document retrieval, GDPR references, and recursive decomposition internally
        const agent = getRLMAgent();
        const rlmResponse = await agent.chat(id, message, conversationHistory);

        console.log(`[Chat] RLM Agent responded: ${rlmResponse.iterations} iteration(s), tools: [${rlmResponse.toolsUsed.join(', ')}]`);

        // Store user message and AI response in database
        await pool.query(
            `INSERT INTO request_chat_messages (request_id, sender, message)
             VALUES ($1, 'user', $2)`,
            [id, message]
        );

        await pool.query(
            `INSERT INTO request_chat_messages (request_id, sender, message)
             VALUES ($1, 'assistant', $2)`,
            [id, rlmResponse.content]
        );

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

