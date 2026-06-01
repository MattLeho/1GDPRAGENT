'use client';

import { useState, useRef, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Send, MessageCircle, Loader2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
}

export function ShadowProfileChat() {
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState<Message[]>([]);
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, loading]);

    const exampleQueries = [
        "Who has my email address?",
        "Show all companies",
        "What data does Amazon have?",
        "Which accounts use my phone number?",
    ];

    const handleSend = async () => {
        if (!input.trim()) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input,
        };

        setMessages((prev) => [...prev, userMessage]);
        setInput('');
        setLoading(true);

        try {
            // Call the graph chat API which uses Gemini + Neo4j
            const response = await fetch('/api/graph/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: input }),
            });

            const data = await response.json();

            let responseContent: string;

            if (!response.ok || data.error) {
                // Fallback to basic graph query if chat API fails
                const graphResponse = await fetch('/api/graph');
                const graphData = await graphResponse.json();

                responseContent = generateLocalResponse(input, graphData);
            } else {
                responseContent = data.response || data.message || "I analyzed your graph but couldn't generate a response.";
            }

            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: responseContent,
            };

            setMessages((prev) => [...prev, assistantMessage]);
        } catch (error) {
            console.error('Chat error:', error);

            // Try local fallback
            try {
                const graphResponse = await fetch('/api/graph');
                const graphData = await graphResponse.json();
                const fallbackResponse = generateLocalResponse(input, graphData);

                const assistantMessage: Message = {
                    id: (Date.now() + 1).toString(),
                    role: 'assistant',
                    content: fallbackResponse,
                };
                setMessages((prev) => [...prev, assistantMessage]);
            } catch {
                toast.error('Failed to get response');
                const errorMessage: Message = {
                    id: (Date.now() + 1).toString(),
                    role: 'assistant',
                    content: "Sorry, I couldn't connect to the graph. Please check if Neo4j is running.",
                };
                setMessages((prev) => [...prev, errorMessage]);
            }
        } finally {
            setLoading(false);
        }
    };

    // Local response generation based on graph data
    const generateLocalResponse = (query: string, graphData: { nodes: unknown[]; links: unknown[] }): string => {
        const lowerQuery = query.toLowerCase();
        const nodes = graphData.nodes as Array<{ type: string; label: string; properties: Record<string, unknown> }>;
        const links = graphData.links as Array<{ type: string; source: string; target: string }>;

        if (nodes.length === 0) {
            return "Your knowledge graph is empty. Start by adding identities and making GDPR requests to build your data map.";
        }

        if (lowerQuery.includes('email')) {
            const emails = nodes.filter(n => n.type === 'Attribute' || n.label?.includes('@'));
            if (emails.length > 0) {
                const accounts = links.filter(l => l.type === 'REGISTERED_WITH' || l.type === 'USES_EMAIL').length;
                return `Found ${emails.length} email addresses in your graph, linked to ${accounts} accounts. These create traceable connections across services.`;
            }
            return "No email addresses found in your graph yet.";
        }

        if (lowerQuery.includes('compan')) {
            const companies = nodes.filter(n => n.type === 'Company');
            if (companies.length > 0) {
                return `Your graph contains ${companies.length} companies: ${companies.map(c => c.label).join(', ')}. Would you like details on any specific company?`;
            }
            return "No companies found in your graph yet. Make GDPR requests to start tracking your data.";
        }

        if (lowerQuery.includes('phone')) {
            const phones = nodes.filter(n => n.type === 'Phone' || n.properties?.type === 'phone');
            if (phones.length > 0) {
                return `Found ${phones.length} phone number(s) in your graph. Phone numbers create strong links between accounts and can be used for identity verification.`;
            }
            return "No phone numbers found in your graph yet.";
        }

        if (lowerQuery.includes('amazon')) {
            const amazon = nodes.find(n => n.label?.toLowerCase().includes('amazon'));
            if (amazon) {
                const relatedLinks = links.filter(l =>
                    l.source === amazon.label || l.target === amazon.label
                );
                return `Amazon is in your graph with ${relatedLinks.length} connections. They likely have purchase history, browsing data, and account information.`;
            }
            return "Amazon is not in your graph yet. Create a GDPR request to Amazon to start tracking.";
        }

        // Generic response with stats
        const personas = nodes.filter(n => n.type === 'Persona').length;
        const accounts = nodes.filter(n => n.type === 'Account').length;
        const companies = nodes.filter(n => n.type === 'Company').length;

        return `Your graph has ${nodes.length} nodes and ${links.length} connections. This includes ${personas} personas, ${accounts} accounts, and ${companies} companies. Ask me about specific emails, companies, or data points.`;
    };

    const handleExampleClick = (query: string) => {
        setInput(query);
    };

    return (
        <Card className="border-t rounded-none bg-white dark:bg-zinc-900">
            <div className="p-4">
                {/* Messages Area */}
                {messages.length > 0 && (
                    <div className="max-h-[60vh] overflow-y-auto mb-4 space-y-3">
                        {messages.map((msg) => (
                            <div
                                key={msg.id}
                                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                            >
                                <div
                                    className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${msg.role === 'user'
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200'
                                        }`}
                                >
                                    {msg.content}
                                </div>
                            </div>
                        ))}
                        {loading && (
                            <div className="flex justify-start">
                                <div className="bg-zinc-100 dark:bg-zinc-800 rounded-lg px-3 py-2">
                                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                                </div>
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>
                )}

                {/* Example Queries */}
                {messages.length === 0 && (
                    <div className="mb-3">
                        <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                            <MessageCircle className="h-3 w-3" />
                            Ask about your data:
                        </p>
                        <div className="flex flex-wrap gap-2">
                            {exampleQueries.map((query) => (
                                <Button
                                    key={query}
                                    variant="outline"
                                    size="sm"
                                    className="text-xs h-7"
                                    onClick={() => handleExampleClick(query)}
                                >
                                    {query}
                                </Button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Input Area */}
                <div className="flex gap-2">
                    <Input
                        placeholder="Ask: 'Who has my phone number?'"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                        disabled={loading}
                        className="flex-1"
                    />
                    <Button onClick={handleSend} disabled={loading || !input.trim()}>
                        <Send className="h-4 w-4" />
                    </Button>
                </div>
            </div>
        </Card>
    );
}
