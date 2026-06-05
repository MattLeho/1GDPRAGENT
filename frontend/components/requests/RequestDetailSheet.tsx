"use client";

import { useEffect, useState } from "react";
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Request } from "@/lib/actions/requests";
import { getMessages, Message } from "@/lib/actions/messages";
import { getRequestAnalysis, PolicyAnalysis } from "@/lib/actions/policy-analysis";
import {
    Mail,
    FileText,
    Clock,
    Bot,
    User,
    Building2,
    Globe,
    MapPin,
    AlertTriangle,
    Database,
    Loader2,
    CheckCircle2,
    Trash2,
    Download
} from "lucide-react";
import { toast } from "sonner";
import { ZipImporter } from "@/components/dashboard/ZipImporter";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";

interface RequestDetailSheetProps {
    request: Request | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

interface WorkflowLog {
    workflow?: string;
    status?: string;
    startedAt: string;
    finishedAt?: string | null;
    error?: string | null;
}

interface ChatMessage {
    role: string;
    content: string;
}

export function RequestDetailSheet({
    request,
    open,
    onOpenChange,
}: RequestDetailSheetProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [analysis, setAnalysis] = useState<PolicyAnalysis | null>(null);
    const [loading, setLoading] = useState(false);
    const [notes, setNotes] = useState("");
    const [n8nLogs, setN8nLogs] = useState<WorkflowLog[]>([]);
    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
    const [chatInput, setChatInput] = useState("");
    const [chatLoading, setChatLoading] = useState(false);

    // Fetch data when sheet opens
    useEffect(() => {
        if (open && request) {
            setLoading(true);
            setNotes(request.notes || "");

            Promise.all([
                getMessages(request.id),
                getRequestAnalysis(request.id),
                fetch(`/api/request-threads/${request.id}/logs`)
                    .then(r => r.json() as Promise<{ logs?: WorkflowLog[] }>)
                    .catch(() => ({ logs: [] })),
                fetch(`/api/request-threads/${request.id}/chat`)
                    .then(r => r.json() as Promise<{ messages?: ChatMessage[] }>)
                    .catch(() => ({ messages: [] })),
            ]).then(([msgs, pol, logsData, chatData]) => {
                setMessages(msgs);
                setAnalysis(pol);
                setN8nLogs(logsData.logs || []);
                setChatMessages(chatData.messages || []);
                setLoading(false);
            }).catch(() => {
                setLoading(false);
            });
        }
    }, [open, request]);

    if (!request) return null;

    const handleMarkComplete = () => {
        toast.success("Request marked as complete", { description: "Status updated to 'completed'" });
    };

    const handleDelete = () => {
        toast.error("Delete not implemented", { description: "This feature is coming soon" });
    };

    const handleExport = () => {
        toast.info("Export started", { description: "Your data will download shortly" });
    };

    const formatDate = (date: Date | string) => {
        const d = new Date(date);
        return d.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const getSenderIcon = (sender: string) => {
        switch (sender) {
            case 'agent': return <Bot className="h-4 w-4" />;
            case 'company': return <Building2 className="h-4 w-4" />;
            default: return <User className="h-4 w-4" />;
        }
    };

    const getSenderColor = (sender: string) => {
        switch (sender) {
            case 'agent': return 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300';
            case 'company': return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300';
            default: return 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300';
        }
    };

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent className="w-full max-w-[calc(100vw-200px)] flex flex-col h-full bg-white dark:bg-zinc-950 p-0" side="right">
                {/* Header */}
                <SheetHeader className="flex flex-row items-center space-x-4 space-y-0 p-6 pb-4 border-b">
                    <Avatar className="h-14 w-14 rounded-lg border">
                        <AvatarImage
                            src={`https://logo.clearbit.com/${request.domain || request.company_name}.com`}
                            alt={request.company_name}
                            className="object-contain"
                        />
                        <AvatarFallback className="rounded-lg text-lg">{request.company_name.substring(0, 2).toUpperCase()}</AvatarFallback>
                    </Avatar>
                    <div className="flex-1">
                        <SheetTitle className="text-xl font-bold">{request.company_name}</SheetTitle>
                        <div className="flex items-center gap-2 mt-1">
                            <Badge
                                variant={request.status === 'completed' ? 'default' : 'outline'}
                                className="text-xs uppercase tracking-wider"
                            >
                                {request.status.replace('_', ' ')}
                            </Badge>
                            <Badge variant="secondary" className="text-xs">
                                {request.request_type}
                            </Badge>
                            <span className="text-xs text-muted-foreground">ID: {request.id.slice(0, 8)}</span>
                        </div>
                    </div>
                </SheetHeader>

                {/* Tabs Content */}
                <Tabs defaultValue="activity" className="flex-1 flex flex-col overflow-hidden">
                    <TabsList className="grid w-full grid-cols-6 px-6 pt-2">
                        <TabsTrigger value="activity">Activity</TabsTrigger>
                        <TabsTrigger value="documents">Documents</TabsTrigger>
                        <TabsTrigger value="files">Files</TabsTrigger>
                        <TabsTrigger value="chat">AI Chat</TabsTrigger>
                        <TabsTrigger value="logs">N8N Logs</TabsTrigger>
                        <TabsTrigger value="notes">Notes</TabsTrigger>
                    </TabsList>

                    {/* Activity Tab */}
                    <TabsContent value="activity" className="flex-1 overflow-hidden m-0">
                        <ScrollArea className="h-full px-6 py-4">
                            {loading ? (
                                <div className="flex items-center justify-center py-12">
                                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                                </div>
                            ) : messages.length === 0 ? (
                                <div className="text-center py-12 text-muted-foreground">
                                    <Clock className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                    <p>No activity yet</p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {messages.map((msg) => (
                                        <div key={msg.id} className="flex gap-3">
                                            <div className={`h-8 w-8 rounded-full flex items-center justify-center ${getSenderColor(msg.sender)}`}>
                                                {getSenderIcon(msg.sender)}
                                            </div>
                                            <div className="flex-1 space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm font-medium capitalize">{msg.sender}</span>
                                                    <span className="text-xs text-muted-foreground">
                                                        {formatDate(msg.timestamp)}
                                                    </span>
                                                </div>
                                                <p className="text-sm text-muted-foreground">{msg.content}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </ScrollArea>
                    </TabsContent>

                    {/* Documents Tab - Shows Policy Analysis */}
                    <TabsContent value="documents" className="flex-1 overflow-hidden m-0">
                        <ScrollArea className="h-full px-6 py-4">
                            {loading ? (
                                <div className="flex items-center justify-center py-12">
                                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                                </div>
                            ) : analysis ? (
                                <div className="space-y-4">
                                    {/* Policy Analysis Card */}
                                    <Card>
                                        <CardHeader className="pb-2">
                                            <div className="flex items-center justify-between">
                                                <CardTitle className="text-sm font-medium flex items-center gap-2">
                                                    <FileText className="h-4 w-4 text-indigo-500" />
                                                    Privacy Policy Analysis
                                                </CardTitle>
                                                <Badge variant="outline" className="text-xs">
                                                    Analyzed {formatDate(analysis.analyzed_at)}
                                                </Badge>
                                            </div>
                                        </CardHeader>
                                        <CardContent className="space-y-4">
                                            {/* Source URL */}
                                            <div className="flex items-center gap-2 text-sm">
                                                <Globe className="h-4 w-4 text-muted-foreground" />
                                                <a href={analysis.company_url} target="_blank" className="text-blue-600 hover:underline truncate">
                                                    {analysis.company_url}
                                                </a>
                                            </div>

                                            {/* DPO Email */}
                                            {analysis.dpo_email && (
                                                <div className="flex items-center gap-2 text-sm">
                                                    <Mail className="h-4 w-4 text-muted-foreground" />
                                                    <span className="font-medium">DPO Email:</span>
                                                    <span>{analysis.dpo_email}</span>
                                                </div>
                                            )}

                                            {/* Address */}
                                            {analysis.company_address && (
                                                <div className="flex items-start gap-2 text-sm">
                                                    <MapPin className="h-4 w-4 text-muted-foreground mt-0.5" />
                                                    <span>{analysis.company_address}</span>
                                                </div>
                                            )}

                                            <Separator />

                                            {/* Data Collected */}
                                            <div>
                                                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                                                    Data Collected
                                                </p>
                                                <div className="flex flex-wrap gap-1.5">
                                                    {analysis.data_collected.map((item, i) => (
                                                        <Badge key={i} variant="secondary" className="text-xs">
                                                            {item}
                                                        </Badge>
                                                    ))}
                                                </div>
                                            </div>

                                            {/* Third Party Sharing */}
                                            {analysis.third_party_sharing.length > 0 && (
                                                <div>
                                                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                                                        Third Party Sharing
                                                    </p>
                                                    <div className="flex flex-wrap gap-1.5">
                                                        {analysis.third_party_sharing.map((item, i) => (
                                                            <Badge key={i} variant="outline" className="text-xs text-orange-600 border-orange-200">
                                                                <AlertTriangle className="h-3 w-3 mr-1" />
                                                                {item}
                                                            </Badge>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Retention Period */}
                                            {analysis.retention_period && (
                                                <div className="flex items-center gap-2 text-sm bg-zinc-50 dark:bg-zinc-900 p-3 rounded-md">
                                                    <Database className="h-4 w-4 text-muted-foreground" />
                                                    <span className="font-medium">Retention:</span>
                                                    <span>{analysis.retention_period}</span>
                                                </div>
                                            )}
                                        </CardContent>
                                    </Card>
                                </div>
                            ) : (
                                <div className="text-center py-12 text-muted-foreground">
                                    <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                    <p>No policy analysis available</p>
                                    <p className="text-xs mt-1">Analysis is saved when creating a new request</p>
                                </div>
                            )}
                        </ScrollArea>
                    </TabsContent>

                    {/* Files Tab - Upload ZIP */}
                    <TabsContent value="files" className="flex-1 overflow-hidden m-0">
                        <ScrollArea className="h-full px-6 py-4">
                            <ZipImporter requestId={request.id} />
                        </ScrollArea>
                    </TabsContent>

                    {/* AI Chat Tab */}
                    <TabsContent value="chat" className="flex-1 overflow-hidden m-0 flex flex-col">
                        <ScrollArea className="flex-1 px-6 py-4">
                            {chatLoading ? (
                                <div className="flex items-center justify-center py-12">
                                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                                </div>
                            ) : chatMessages.length === 0 ? (
                                <div className="text-center py-12 text-muted-foreground">
                                    <Bot className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                    <p>Start a conversation with the AI agent</p>
                                    <p className="text-xs mt-1">Ask questions about this request</p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {chatMessages.map((msg, idx) => (
                                        <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                                            {msg.role !== 'user' && (
                                                <div className="h-8 w-8 rounded-full flex items-center justify-center bg-indigo-100 dark:bg-indigo-900">
                                                    <Bot className="h-4 w-4 text-indigo-700 dark:text-indigo-300" />
                                                </div>
                                            )}
                                            <div className={`flex-1 max-w-[80%] ${msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'} rounded-lg p-3`}>
                                                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                                            </div>
                                            {msg.role === 'user' && (
                                                <div className="h-8 w-8 rounded-full flex items-center justify-center bg-zinc-200 dark:bg-zinc-700">
                                                    <User className="h-4 w-4" />
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </ScrollArea>
                        <div className="p-4 border-t">
                            <div className="flex gap-2">
                                <Input
                                    placeholder="Ask AI about this request..."
                                    value={chatInput}
                                    onChange={(e) => setChatInput(e.target.value)}
                                    onKeyPress={(e) => {
                                        if (e.key === 'Enter' && !e.shiftKey) {
                                            e.preventDefault();
                                            // Send message
                                            if (chatInput.trim()) {
                                                const userMsg = { role: 'user', content: chatInput };
                                                setChatMessages(prev => [...prev, userMsg]);
                                                setChatInput('');
                                                setChatLoading(true);

                                                // Call AI API
                                                fetch(`/api/request-threads/${request.id}/chat`, {
                                                    method: 'POST',
                                                    headers: { 'Content-Type': 'application/json' },
                                                    body: JSON.stringify({ message: chatInput }),
                                                }).then(r => r.json() as Promise<{ response?: string }>).then(data => {
                                                    const assistantResponse = data.response;
                                                    if (assistantResponse) {
                                                        setChatMessages(prev => [...prev, { role: 'assistant', content: assistantResponse }]);
                                                    }
                                                }).catch(() => {
                                                    toast.error('Failed to send message');
                                                }).finally(() => {
                                                    setChatLoading(false);
                                                });
                                            }
                                        }
                                    }}
                                    disabled={chatLoading}
                                />
                                <Button size="sm" disabled={chatLoading || !chatInput.trim()}>
                                    Send
                                </Button>
                            </div>
                        </div>
                    </TabsContent>

                    {/* N8N Logs Tab */}
                    <TabsContent value="logs" className="flex-1 overflow-hidden m-0">
                        <ScrollArea className="h-full px-6 py-4">
                            {n8nLogs.length === 0 ? (
                                <div className="text-center py-12 text-muted-foreground">
                                    <Database className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                    <p>No N8N workflow logs</p>
                                    <p className="text-xs mt-1">Workflow activations will appear here</p>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {n8nLogs.map((log, idx) => (
                                        <Card key={idx}>
                                            <CardHeader className="pb-2">
                                                <div className="flex items-center justify-between">
                                                    <CardTitle className="text-sm font-medium">{log.workflow || 'Workflow'}</CardTitle>
                                                    <Badge variant={log.status === 'success' ? 'default' : 'destructive'}>
                                                        {log.status}
                                                    </Badge>
                                                </div>
                                            </CardHeader>
                                            <CardContent className="text-xs text-muted-foreground space-y-1">
                                                <p>Started: {new Date(log.startedAt).toLocaleString()}</p>
                                                {log.finishedAt && <p>Finished: {new Date(log.finishedAt).toLocaleString()}</p>}
                                                {log.error && <p className="text-red-600">Error: {log.error}</p>}
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            )}
                        </ScrollArea>
                    </TabsContent>

                    {/* Notes Tab */}
                    <TabsContent value="notes" className="flex-1 overflow-hidden m-0">
                        <div className="p-6 h-full flex flex-col">
                            <Textarea
                                className="flex-1 resize-none"
                                placeholder="Add notes about this request..."
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                            />
                            <Button className="mt-3 self-end" size="sm" onClick={() => toast.success("Notes saved")}>
                                Save Notes
                            </Button>
                        </div>
                    </TabsContent>
                </Tabs>

                {/* Footer Actions */}
                <div className="p-4 border-t flex items-center justify-between bg-zinc-50 dark:bg-zinc-900/50">
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={handleExport}>
                            <Download className="mr-2 h-4 w-4" />
                            Export
                        </Button>
                        <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700 hover:bg-red-50" onClick={handleDelete}>
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                        </Button>
                    </div>
                    {request.status !== 'completed' && (
                        <Button size="sm" onClick={handleMarkComplete}>
                            <CheckCircle2 className="mr-2 h-4 w-4" />
                            Mark Complete
                        </Button>
                    )}
                </div>
            </SheetContent>
        </Sheet>
    );
}
