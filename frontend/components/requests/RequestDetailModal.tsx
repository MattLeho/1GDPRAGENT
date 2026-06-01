"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";
import { Request } from "@/lib/actions/requests";
import { getMessages, Message } from "@/lib/actions/messages";
import { getRequestAnalysis, PolicyAnalysis } from "@/lib/actions/policy-analysis";
import { getReceivedData } from "@/lib/actions/data";
import {
    Mail, FileText, Clock, Bot, User, Building2,
    AlertTriangle, Database, Loader2, CheckCircle2, Download,
    MessageSquare, File, Image, FileSpreadsheet, FileAudio,
    Eye, Upload, Sparkles, X, Bell, Workflow, FileCheck,
    Activity, RefreshCw, ChevronRight, Send, Trash2, Search
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface RequestDetailModalProps {
    request: Request | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

interface ActivityLog {
    id: string;
    type: 'workflow' | 'event' | 'file';
    title: string;
    description: string;
    status: string;
    timestamp: string;
    progress?: number;
    graphIngested?: boolean;
    error?: string;
    details?: any;
}

export function RequestDetailModal({ request, open, onOpenChange }: RequestDetailModalProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [analysis, setAnalysis] = useState<PolicyAnalysis | null>(null);
    const [receivedData, setReceivedData] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
    const [enhanceGraph, setEnhanceGraph] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
    const [isProcessing, setIsProcessing] = useState(false);
    const [processingStage, setProcessingStage] = useState<string>('upload');
    const [previewFile, setPreviewFile] = useState<any>(null);
    const [chatMessages, setChatMessages] = useState<any[]>([]);
    const [chatInput, setChatInput] = useState("");
    const [chatLoading, setChatLoading] = useState(false);
    const [activities, setActivities] = useState<ActivityLog[]>([]);
    const [activitiesLoading, setActivitiesLoading] = useState(false);
    const [scanning, setScanning] = useState(false);
    const chatEndRef = useRef<HTMLDivElement>(null);
    const graphIngestTriggered = useRef<Set<string>>(new Set());

    // Helper to fetch files from GET endpoint (consistent camelCase format)
    const fetchFiles = useCallback(async (reqId: string) => {
        try {
            const res = await fetch(`/api/upload?requestId=${reqId}`);
            if (res.ok) {
                const data = await res.json();
                return data.files || [];
            }
        } catch { /* ignore */ }
        return [];
    }, []);

    // Fetch all data when modal opens
    useEffect(() => {
        if (open && request) {
            setLoading(true);
            graphIngestTriggered.current.clear();
            Promise.all([
                getMessages(request.id),
                getRequestAnalysis(request.id),
                fetchFiles(request.id),
                fetch(`/api/request-threads/${request.id}/chat`).then(r => r.ok ? r.json() : { messages: [] }).catch(() => ({ messages: [] })),
                fetch(`/api/requests/${request.id}/logs`).then(r => r.ok ? r.json() : { activities: [] }).catch(() => ({ activities: [] })),
            ]).then(([msgs, pol, files, chatData, logsData]) => {
                setMessages(msgs);
                setAnalysis(pol);
                setReceivedData(files);
                setChatMessages(chatData.messages || []);
                setActivities(logsData.activities || []);
                setLoading(false);
                // Check if any files are still processing
                const hasProcessing = files.some((f: any) => f.status === 'processing' || f.status === 'pending');
                if (hasProcessing) setIsProcessing(true);
            }).catch(() => setLoading(false));
        }
    }, [open, request, fetchFiles]);

    // Auto-scroll chat to bottom
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [chatMessages]);

    // Processing-aware polling: faster (3s) when processing, slower (10s) when idle
    useEffect(() => {
        if (!open || !request) return;
        const pollInterval = isProcessing ? 3000 : 10000;
        const interval = setInterval(async () => {
            // Refresh activities
            fetch(`/api/requests/${request.id}/logs`)
                .then(r => r.ok ? r.json() : { activities: [] })
                .then(data => setActivities(data.activities || []))
                .catch(() => { });

            // Refresh files
            const files = await fetchFiles(request.id);
            if (files.length > 0) {
                setReceivedData(files);

                // Determine overall processing stage from files
                const stages = files.map((f: any) => f.processingStage || 'upload');
                const hasIngest = stages.includes('ingest');
                const hasAnalyze = stages.includes('analyze');
                const hasExtract = stages.includes('extract') || stages.includes('transcribe') || stages.includes('parse');
                if (hasIngest) setProcessingStage('ingest');
                else if (hasAnalyze) setProcessingStage('analyze');
                else if (hasExtract) setProcessingStage('extract');
                else setProcessingStage('upload');

                // Check if all files are done processing (completed or error)
                const allDone = files.every((f: any) => f.status === 'completed' || f.status === 'error');
                if (allDone && isProcessing) {
                    setIsProcessing(false);
                    setProcessingStage('completed');

                    // Auto-trigger graph ingestion for completed files if enhanceGraph is on
                    if (enhanceGraph) {
                        for (const file of files) {
                            if (file.status === 'completed' && !file.graphIngested && !graphIngestTriggered.current.has(file.id)) {
                                graphIngestTriggered.current.add(file.id);
                                fetch('/api/upload/process', {
                                    method: 'PUT',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ fileId: file.id }),
                                }).catch(err => console.error('Graph ingestion failed:', err));
                            }
                        }
                    }
                }
            }
        }, pollInterval);
        return () => clearInterval(interval);
    }, [open, request, isProcessing, enhanceGraph, fetchFiles]);

    const onDrop = useCallback((files: File[]) => {
        setUploadedFiles(prev => [...prev, ...files]);
        toast.success(`Added ${files.length} file(s)`);
    }, []);

    const handleDeleteFile = useCallback(async (fileId: string, fileName: string) => {
        if (!confirm(`Delete "${fileName}"? This cannot be undone.`)) return;
        try {
            const res = await fetch(`/api/upload?fileId=${fileId}`, { method: 'DELETE' });
            if (res.ok) {
                setReceivedData(prev => prev.filter(f => f.id !== fileId));
                if (previewFile?.id === fileId) setPreviewFile(null);
                toast.success(`Deleted ${fileName}`);
            } else {
                toast.error('Failed to delete file');
            }
        } catch {
            toast.error('Failed to delete file');
        }
    }, [previewFile]);

    const handleScanAll = useCallback(async () => {
        setScanning(true);
        try {
            const res = await fetch('/api/upload/scan', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                toast.success(data.message);
                // Refresh the file list
                if (request) {
                    const files = await fetchFiles(request.id);
                    if (files.length > 0) setReceivedData(files);
                }
            } else {
                toast.error(data.error || 'Scan failed');
            }
        } catch {
            toast.error('Scan failed');
        } finally {
            setScanning(false);
        }
    }, [request, fetchFiles]);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

    const handleUpload = async () => {
        if (uploadedFiles.length === 0 || !request) return;
        setUploading(true);

        // Initialize progress for each file
        const progressInit: Record<string, number> = {};
        uploadedFiles.forEach((f, i) => progressInit[i] = 0);
        setUploadProgress(progressInit);

        try {
            const formData = new FormData();
            uploadedFiles.forEach(file => formData.append('files', file));
            formData.append('requestId', request.id);

            // Simulate progress updates
            const progressInterval = setInterval(() => {
                setUploadProgress(prev => {
                    const next = { ...prev };
                    Object.keys(next).forEach(key => {
                        if (next[key] < 90) next[key] += Math.random() * 15;
                    });
                    return next;
                });
            }, 200);

            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
            });

            clearInterval(progressInterval);
            setUploadProgress(prev => {
                const next = { ...prev };
                Object.keys(next).forEach(key => next[key] = 100);
                return next;
            });

            const data = await res.json();

            if (data.success) {
                toast.success(`Uploaded ${data.totalFiles} file(s)`, {
                    description: 'Files will be automatically processed' + (enhanceGraph ? ' and added to knowledge graph' : '')
                });

                // ALWAYS trigger processing for ALL uploaded files
                setIsProcessing(true);
                setProcessingStage('upload');
                for (const file of data.files) {
                    fetch('/api/upload/process', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ fileId: file.id }),
                    }).catch(err => console.error('Failed to trigger processing:', err));
                }

                // Refresh files list
                const files = await fetchFiles(request.id);
                setReceivedData(files);

                setUploadedFiles([]);
                setUploadProgress({});
            } else {
                toast.error('Upload failed', { description: data.error });
            }
        } catch (error) {
            toast.error('Upload failed', { description: 'Network error' });
        } finally {
            setUploading(false);
        }
    };

    const sendChatMessage = async () => {
        if (!chatInput.trim() || chatLoading || !request) return;

        const message = chatInput.trim();
        setChatMessages(prev => [...prev, { role: 'user', content: message, timestamp: new Date().toISOString() }]);
        setChatInput('');
        setChatLoading(true);

        try {
            const res = await fetch(`/api/request-threads/${request.id}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message }),
            });
            const data = await res.json();
            if (data.response) {
                setChatMessages(prev => [...prev, {
                    role: 'assistant',
                    content: data.response,
                    timestamp: new Date().toISOString()
                }]);
            }
        } catch {
            toast.error('Failed to send message');
        } finally {
            setChatLoading(false);
        }
    };

    if (!request) return null;

    const formatDate = (date: Date | string) => new Date(date).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });

    const createdAt = new Date(request.created_at);
    const daysPassed = Math.floor((Date.now() - createdAt.getTime()) / (1000 * 60 * 60 * 24));
    const progress = Math.min(100, (daysPassed / 30) * 100);
    const daysRemaining = Math.max(0, 30 - daysPassed);

    const getTimelineStatus = () => {
        if (request.status === 'completed') return { label: 'Completed', color: 'text-green-600' };
        if (daysPassed <= 7) return { label: 'Awaiting Response', color: 'text-yellow-600' };
        if (daysPassed <= 21) return { label: 'Processing', color: 'text-blue-600' };
        return { label: 'Deadline Near', color: 'text-red-600' };
    };
    const timelineStatus = getTimelineStatus();

    const getFileIcon = (type: string) => {
        if (type?.includes('pdf') || type?.includes('document')) return <FileText className="h-4 w-4 text-red-500" />;
        if (type?.includes('image') || type?.includes('photo') || type?.includes('png') || type?.includes('jpg')) return <Image className="h-4 w-4 text-blue-500" />;
        if (type?.includes('spreadsheet') || type?.includes('csv') || type?.includes('excel') || type?.includes('xlsx')) return <FileSpreadsheet className="h-4 w-4 text-green-500" />;
        if (type?.includes('audio') || type?.includes('mp3') || type?.includes('wav') || type?.includes('m4a')) return <FileAudio className="h-4 w-4 text-purple-500" />;
        if (type?.includes('video') || type?.includes('mp4')) return <File className="h-4 w-4 text-pink-500" />;
        if (type?.includes('zip') || type?.includes('archive') || type?.includes('rar')) return <File className="h-4 w-4 text-amber-500" />;
        return <File className="h-4 w-4 text-zinc-500" />;
    };

    // File-type-specific animation variants for upload items
    const getFileTypeAnimation = (fileName: string) => {
        const ext = fileName.toLowerCase();
        if (ext.includes('.pdf') || ext.includes('.doc')) {
            return {
                animate: { opacity: [0.8, 1, 0.8], boxShadow: ['0 0 0 0 rgba(239,68,68,0)', '0 0 8px 2px rgba(239,68,68,0.25)', '0 0 0 0 rgba(239,68,68,0)'] },
                transition: { repeat: Infinity, duration: 2 },
            };
        }
        if (ext.includes('.png') || ext.includes('.jpg') || ext.includes('.jpeg') || ext.includes('.gif') || ext.includes('.webp')) {
            return {
                animate: { background: ['linear-gradient(135deg, rgba(59,130,246,0.05), rgba(59,130,246,0.1))', 'linear-gradient(135deg, rgba(59,130,246,0.1), rgba(59,130,246,0.05))'] },
                transition: { repeat: Infinity, duration: 1.5 },
            };
        }
        if (ext.includes('.csv') || ext.includes('.xlsx') || ext.includes('.xls')) {
            return {
                animate: { y: [0, -2, 0] },
                transition: { repeat: Infinity, duration: 1, ease: 'easeInOut' as const },
            };
        }
        if (ext.includes('.mp3') || ext.includes('.wav') || ext.includes('.m4a') || ext.includes('.ogg')) {
            return {
                animate: { scaleY: [1, 1.05, 0.95, 1.05, 1] },
                transition: { repeat: Infinity, duration: 1.2, ease: 'easeInOut' as const },
            };
        }
        return {
            animate: { rotate: [0, 5, -5, 0] },
            transition: { repeat: Infinity, duration: 3 },
        };
    };

    // Stage-specific icons for the processing pipeline
    const getStageIcon = (stage: string, isDone: boolean) => {
        if (isDone) return <CheckCircle2 className="h-4 w-4" />;
        switch (stage) {
            case 'upload': return <Upload className="h-4 w-4" />;
            case 'extract': return <FileText className="h-4 w-4" />;
            case 'analyze': return <Sparkles className="h-4 w-4" />;
            case 'ingest': return <Database className="h-4 w-4" />;
            default: return <Activity className="h-4 w-4" />;
        }
    };

    // Per-stage animation variants for the pipeline
    const getStageAnimation = (stage: string) => {
        switch (stage) {
            case 'upload': return { y: [0, -4, 0], transition: { repeat: Infinity, duration: 0.8 } };
            case 'extract': return { x: [-2, 2, -2], transition: { repeat: Infinity, duration: 0.6 } };
            case 'analyze': return { rotate: [0, 360], transition: { repeat: Infinity, duration: 2.5, ease: 'linear' as const } };
            case 'ingest': return { scale: [1, 1.2, 1], transition: { repeat: Infinity, duration: 1 } };
            default: return { scale: [1, 1.1, 1], transition: { repeat: Infinity, duration: 1.2 } };
        }
    };

    // Stage description for active processing
    const getStageDescription = (stage: string) => {
        switch (stage) {
            case 'upload': return 'Files are being uploaded to the server...';
            case 'extract': return 'Extracting text, metadata, and content from files...';
            case 'analyze': return 'AI is analyzing content and generating summaries...';
            case 'ingest': return 'Ingesting entities and relationships into the knowledge graph...';
            case 'completed': return 'All files have been processed successfully!';
            default: return 'Processing...';
        }
    };

    const getProcessingStageLabel = (stage: string) => {
        switch (stage) {
            case 'upload': return 'Uploading...';
            case 'extract': return 'Extracting text...';
            case 'transcribe': return 'Transcribing...';
            case 'parse': return 'Parsing...';
            case 'analyze': return 'Analyzing...';
            case 'ingest': return 'Ingesting to graph...';
            case 'completed': return 'Complete';
            default: return stage;
        }
    };

    const getStatusBadge = (status: string, progress?: number, stage?: string) => {
        switch (status) {
            case 'pending':
                return <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200"><Clock className="h-3 w-3 mr-1" />Pending</Badge>;
            case 'processing':
                return (
                    <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                        <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        {stage ? getProcessingStageLabel(stage) : `Processing${progress ? ` ${progress}%` : ''}`}
                    </Badge>
                );
            case 'completed':
                return <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200"><CheckCircle2 className="h-3 w-3 mr-1" />Complete</Badge>;
            case 'error':
                return <Badge variant="destructive"><AlertTriangle className="h-3 w-3 mr-1" />Error</Badge>;
            default:
                return <Badge variant="secondary">{status}</Badge>;
        }
    };

    const getActivityIcon = (type: string, status: string) => {
        if (status === 'error') return <AlertTriangle className="h-4 w-4 text-red-500" />;
        switch (type) {
            case 'workflow': return <Workflow className="h-4 w-4 text-purple-500" />;
            case 'file': return <FileCheck className="h-4 w-4 text-blue-500" />;
            case 'event': return <Activity className="h-4 w-4 text-green-500" />;
            default: return <Bell className="h-4 w-4 text-zinc-500" />;
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent data-full-width="true" className="w-[calc(100vw-256px)] flex flex-col p-0 gap-0">
                {/* Header */}
                <DialogHeader className="flex flex-row items-center gap-4 p-6 pb-4 border-b shrink-0">
                    <Avatar className="h-14 w-14 rounded-lg border">
                        <AvatarImage src={`https://logo.clearbit.com/${request.domain || request.company_name}.com`} />
                        <AvatarFallback className="rounded-lg text-lg">{request.company_name.substring(0, 2).toUpperCase()}</AvatarFallback>
                    </Avatar>
                    <div className="flex-1">
                        <DialogTitle className="text-xl font-bold">{request.company_name}</DialogTitle>
                        <div className="flex items-center gap-2 mt-1">
                            <Badge variant={request.status === 'completed' ? 'default' : 'outline'}>{request.status.replace('_', ' ')}</Badge>
                            <Badge variant="secondary">{request.request_type}</Badge>
                        </div>
                    </div>
                    <div className="text-right">
                        <p className={`text-sm font-medium ${timelineStatus.color}`}>{timelineStatus.label}</p>
                        <div className="flex items-center gap-2 mt-1">
                            <Progress value={progress} className="w-32 h-2" />
                            <span className="text-xs text-muted-foreground">{daysRemaining}d left</span>
                        </div>
                    </div>
                </DialogHeader>

                {/* Main Content */}
                <div className="flex-1 flex overflow-hidden min-h-0">
                    {/* Left Panel - Activity Log */}
                    <div className="w-2/5 border-r flex flex-col overflow-hidden min-h-0">
                        <div className="p-4 border-b bg-muted/30 flex items-center justify-between">
                            <h3 className="text-sm font-semibold flex items-center gap-2">
                                <Bell className="h-4 w-4" /> Notifications
                            </h3>
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => {
                                setActivitiesLoading(true);
                                fetch(`/api/requests/${request.id}/logs`)
                                    .then(r => r.json())
                                    .then(data => setActivities(data.activities || []))
                                    .finally(() => setActivitiesLoading(false));
                            }}>
                                <RefreshCw className={cn("h-3.5 w-3.5", activitiesLoading && "animate-spin")} />
                            </Button>
                        </div>
                        <ScrollArea className="flex-1">
                            {loading ? (
                                <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin" /></div>
                            ) : activities.length === 0 && messages.length === 0 ? (
                                <div className="text-center py-8 text-muted-foreground">
                                    <Clock className="h-8 w-8 mx-auto mb-2 opacity-50" /><p>No activity yet</p>
                                </div>
                            ) : (
                                <div className="p-4 space-y-3">
                                    <AnimatePresence>
                                        {activities.map((activity, idx) => (
                                            <motion.div
                                                key={activity.id}
                                                initial={{ opacity: 0, y: -10 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                exit={{ opacity: 0, y: 10 }}
                                                transition={{ delay: idx * 0.05 }}
                                                className={cn(
                                                    "flex gap-3 p-3 rounded-lg border bg-card hover:bg-muted/50 transition-colors",
                                                    activity.status === 'error' && "border-red-200 bg-red-50/50"
                                                )}
                                            >
                                                <div className={cn(
                                                    "h-8 w-8 rounded-full flex items-center justify-center shrink-0",
                                                    activity.status === 'error' ? "bg-red-100" :
                                                        activity.status === 'completed' ? "bg-green-100" :
                                                            activity.status === 'processing' ? "bg-blue-100" : "bg-zinc-100"
                                                )}>
                                                    {getActivityIcon(activity.type, activity.status)}
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <p className="text-sm font-medium truncate">{activity.title}</p>
                                                        {getStatusBadge(activity.status, activity.progress)}
                                                    </div>
                                                    <p className="text-xs text-muted-foreground mt-0.5">{activity.description}</p>
                                                    {activity.progress && activity.status === 'processing' && (
                                                        <Progress value={activity.progress} className="h-1 mt-2" />
                                                    )}
                                                    {activity.graphIngested && (
                                                        <Badge variant="secondary" className="text-xs mt-1">
                                                            <Database className="h-3 w-3 mr-1" />Graph Synced
                                                        </Badge>
                                                    )}
                                                    {activity.error && (
                                                        <p className="text-xs text-red-600 mt-1">{activity.error}</p>
                                                    )}
                                                    <p className="text-xs text-muted-foreground mt-1">
                                                        {activity.timestamp && formatDate(activity.timestamp)}
                                                    </p>
                                                </div>
                                            </motion.div>
                                        ))}
                                    </AnimatePresence>

                                    {/* Legacy messages */}
                                    {messages.map((msg) => (
                                        <div key={msg.id} className="flex gap-3 p-3 rounded-lg border bg-card">
                                            <div className="h-8 w-8 rounded-full flex items-center justify-center shrink-0 bg-indigo-100">
                                                {msg.sender === 'agent' ? <Bot className="h-4 w-4 text-indigo-600" /> :
                                                    msg.sender === 'company' ? <Building2 className="h-4 w-4 text-green-600" /> :
                                                        <User className="h-4 w-4 text-zinc-600" />}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm">{msg.content}</p>
                                                <p className="text-xs text-muted-foreground mt-1">{formatDate(msg.timestamp)}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </ScrollArea>
                    </div>

                    {/* Right Panel - Tabs */}
                    <div className="w-3/5 flex flex-col">
                        <Tabs defaultValue="files" className="flex-1 flex flex-col">
                            <TabsList className="mx-4 mt-4 shrink-0">
                                <TabsTrigger value="files">Files & Data</TabsTrigger>
                                <TabsTrigger value="upload">Upload</TabsTrigger>
                                <TabsTrigger value="chat">AI Chat</TabsTrigger>
                                <TabsTrigger value="analysis">Policy</TabsTrigger>
                            </TabsList>

                            {/* Files Tab */}
                            <TabsContent value="files" className="flex-1 overflow-hidden m-0">
                                <ScrollArea className="h-full p-4">
                                    {receivedData.length > 0 && (
                                        <div className="flex justify-end mb-3">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={handleScanAll}
                                                disabled={scanning}
                                                className="gap-2"
                                            >
                                                {scanning ? (
                                                    <><Loader2 className="h-3 w-3 animate-spin" />Processing...</>
                                                ) : (
                                                    <><RefreshCw className="h-3 w-3" />Scan & Process All</>
                                                )}
                                            </Button>
                                        </div>
                                    )}
                                    {receivedData.length === 0 ? (
                                        <div className="text-center py-12 text-muted-foreground">
                                            <Database className="h-10 w-10 mx-auto mb-3 opacity-50" />
                                            <p className="font-medium">No files yet</p>
                                            <p className="text-xs mt-1">Upload files in the Upload tab</p>
                                        </div>
                                    ) : (
                                        <div className="space-y-2">
                                            {receivedData.map((file: any, i: number) => (
                                                <div key={file.id || i}>
                                                    <motion.div
                                                        initial={{ opacity: 0, y: 10 }}
                                                        animate={{ opacity: 1, y: 0 }}
                                                        transition={{ delay: i * 0.05 }}
                                                        className="flex items-center gap-3 p-3 rounded-lg border hover:bg-muted/50 transition-colors"
                                                    >
                                                        <div className="h-10 w-10 rounded-lg bg-muted flex items-center justify-center">
                                                            {getFileIcon(file.fileType || file.category)}
                                                        </div>
                                                        <div className="flex-1 min-w-0">
                                                            <p className="text-sm font-medium truncate">{file.fileName || file.originalName}</p>
                                                            <div className="flex items-center gap-2 mt-0.5">
                                                                <span className="text-xs text-muted-foreground">
                                                                    {file.fileSizeMb ? `${file.fileSizeMb.toFixed(2)} MB` : 'Unknown size'}
                                                                </span>
                                                                {file.category && (
                                                                    <Badge variant="secondary" className="text-xs">{file.category}</Badge>
                                                                )}
                                                            </div>
                                                            {file.status === 'processing' && file.processingProgress > 0 && (
                                                                <Progress value={file.processingProgress} className="h-1 mt-2" />
                                                            )}
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            {getStatusBadge(file.status || 'completed', file.processingProgress, file.processingStage)}
                                                            {file.graphIngested && (
                                                                <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200">
                                                                    <Database className="h-3 w-3 mr-1" />Synced
                                                                </Badge>
                                                            )}
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="h-8 w-8"
                                                                onClick={() => setPreviewFile(previewFile?.id === file.id ? null : file)}
                                                            >
                                                                <Eye className={cn("h-4 w-4", previewFile?.id === file.id && "text-primary")} />
                                                            </Button>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="h-8 w-8 text-muted-foreground hover:text-red-600"
                                                                onClick={() => handleDeleteFile(file.id, file.fileName || file.originalName)}
                                                            >
                                                                <Trash2 className="h-4 w-4" />
                                                            </Button>
                                                        </div>
                                                    </motion.div>
                                                    {/* Inline File Preview */}
                                                    <AnimatePresence>
                                                        {previewFile?.id === file.id && (
                                                            <motion.div
                                                                initial={{ opacity: 0, height: 0 }}
                                                                animate={{ opacity: 1, height: 'auto' }}
                                                                exit={{ opacity: 0, height: 0 }}
                                                                className="overflow-hidden"
                                                            >
                                                                <div className="p-4 rounded-lg border bg-muted/30 space-y-3 mt-1">
                                                                    {file.status === 'error' && file.errorMessage && (
                                                                        <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
                                                                            <AlertTriangle className="h-3 w-3 inline mr-1" />{file.errorMessage}
                                                                        </div>
                                                                    )}
                                                                    {file.aiSummary && (
                                                                        <div>
                                                                            <p className="text-xs font-medium text-muted-foreground mb-1">AI Summary</p>
                                                                            <p className="text-sm">{file.aiSummary}</p>
                                                                        </div>
                                                                    )}
                                                                    {file.transcript && (
                                                                        <div>
                                                                            <p className="text-xs font-medium text-muted-foreground mb-1">Transcript</p>
                                                                            <pre className="text-xs whitespace-pre-wrap max-h-48 overflow-y-auto bg-background p-2 rounded border">{file.transcript.substring(0, 2000)}{file.transcript.length > 2000 ? '...' : ''}</pre>
                                                                        </div>
                                                                    )}
                                                                    {file.extractedText && !file.transcript && (
                                                                        <div>
                                                                            <p className="text-xs font-medium text-muted-foreground mb-1">Extracted Text</p>
                                                                            <pre className="text-xs whitespace-pre-wrap max-h-48 overflow-y-auto bg-background p-2 rounded border">{file.extractedText.substring(0, 2000)}{file.extractedText.length > 2000 ? '...' : ''}</pre>
                                                                        </div>
                                                                    )}
                                                                    {file.status === 'pending' && (
                                                                        <p className="text-sm text-muted-foreground italic">File has not been processed yet.</p>
                                                                    )}
                                                                    {file.status === 'processing' && (
                                                                        <div className="flex items-center gap-2 text-sm text-blue-600">
                                                                            <Loader2 className="h-4 w-4 animate-spin" />
                                                                            {getProcessingStageLabel(file.processingStage || 'processing')}
                                                                        </div>
                                                                    )}
                                                                    {!file.aiSummary && !file.extractedText && !file.transcript && file.status === 'completed' && (
                                                                        <p className="text-sm text-muted-foreground italic">No extracted content available.</p>
                                                                    )}
                                                                </div>
                                                            </motion.div>
                                                        )}
                                                    </AnimatePresence>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </ScrollArea>
                            </TabsContent>

                            {/* Upload Tab */}
                            <TabsContent value="upload" className="flex-1 overflow-hidden m-0">
                                <ScrollArea className="h-full p-4">
                                    <div {...getRootProps()}>
                                        <motion.div
                                            className={cn(
                                                'border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all mb-3',
                                                isDragActive
                                                    ? 'border-primary bg-primary/5 scale-[1.02]'
                                                    : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/30'
                                            )}
                                            whileHover={{ scale: 1.01 }}
                                            whileTap={{ scale: 0.99 }}
                                        >
                                            <input {...getInputProps()} />
                                            <motion.div
                                                animate={isDragActive ? { y: -5 } : { y: 0 }}
                                                transition={{ type: "spring", stiffness: 300 }}
                                            >
                                                <Upload className={cn(
                                                    "h-8 w-8 mx-auto mb-2 transition-colors",
                                                    isDragActive ? "text-primary" : "text-muted-foreground"
                                                )} />
                                                <p className="text-sm font-medium">
                                                    {isDragActive ? "Drop files here" : "Drop files here or click to browse"}
                                                </p>
                                                <p className="text-xs text-muted-foreground mt-1">
                                                    PDF, images, audio, spreadsheets supported
                                                </p>
                                            </motion.div>
                                        </motion.div>
                                    </div>

                                    {/* Upload button + graph toggle — always visible right after dropzone */}
                                    <div className="flex items-center gap-3 mb-3">
                                        <div className="flex items-center gap-2 flex-1">
                                            <Checkbox id="enhance" checked={enhanceGraph} onCheckedChange={(v) => setEnhanceGraph(!!v)} />
                                            <label htmlFor="enhance" className="text-xs flex items-center gap-1 cursor-pointer">
                                                <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                                                Add to knowledge graph
                                            </label>
                                        </div>
                                        {uploadedFiles.length > 0 && (
                                            <Button onClick={handleUpload} disabled={uploading} size="sm">
                                                {uploading ? (
                                                    <>
                                                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                                                        Uploading...
                                                    </>
                                                ) : (
                                                    <>
                                                        <Upload className="mr-1.5 h-3.5 w-3.5" />
                                                        Upload {uploadedFiles.length} file(s)
                                                    </>
                                                )}
                                            </Button>
                                        )}
                                    </div>

                                    {/* Files being uploaded — scrollable list */}
                                    <AnimatePresence>
                                        {uploadedFiles.length > 0 && (
                                            <motion.div
                                                initial={{ opacity: 0, height: 0 }}
                                                animate={{ opacity: 1, height: 'auto' }}
                                                exit={{ opacity: 0, height: 0 }}
                                                className="space-y-2 mb-3 max-h-52 overflow-y-auto pr-1"
                                            >
                                                {uploadedFiles.map((f, i) => (
                                                    <motion.div
                                                        key={i}
                                                        initial={{ opacity: 0, x: -20 }}
                                                        animate={{ opacity: 1, x: 0 }}
                                                        exit={{ opacity: 0, x: 20 }}
                                                        className="flex items-center gap-2 p-2.5 rounded-lg bg-muted/50 border"
                                                    >
                                                        <motion.div
                                                            {...(uploading ? getFileTypeAnimation(f.name) : {})}
                                                            className="flex items-center justify-center"
                                                        >
                                                            {getFileIcon(f.type)}
                                                        </motion.div>
                                                        <div className="flex-1 min-w-0">
                                                            <p className="text-sm truncate">{f.name}</p>
                                                            {uploading && uploadProgress[i] !== undefined && (
                                                                <div className="flex items-center gap-2 mt-1">
                                                                    <Progress value={uploadProgress[i]} className="h-1 flex-1" />
                                                                    <span className="text-xs text-muted-foreground">
                                                                        {Math.round(uploadProgress[i])}%
                                                                    </span>
                                                                </div>
                                                            )}
                                                        </div>
                                                        {!uploading && (
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="h-6 w-6"
                                                                onClick={() => setUploadedFiles(prev => prev.filter((_, idx) => idx !== i))}
                                                            >
                                                                <X className="h-3 w-3" />
                                                            </Button>
                                                        )}
                                                    </motion.div>
                                                ))}
                                            </motion.div>
                                        )}
                                    </AnimatePresence>

                                    {/* Processing Pipeline Visualization */}
                                    <AnimatePresence>
                                        {(uploading || isProcessing) && (
                                            <motion.div
                                                initial={{ opacity: 0, y: 20 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                exit={{ opacity: 0, y: -10 }}
                                                className="mt-6 p-4 rounded-lg border bg-muted/30"
                                            >
                                                <div className="flex items-center justify-between mb-3">
                                                    <p className="text-xs font-medium text-muted-foreground">PROCESSING PIPELINE</p>
                                                    {isProcessing && (
                                                        <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 text-xs">
                                                            <Loader2 className="h-3 w-3 mr-1 animate-spin" />Active
                                                        </Badge>
                                                    )}
                                                </div>
                                                <div className="flex items-center justify-between gap-1">
                                                    {(() => {
                                                        const pipelineStages = ['upload', 'extract', 'analyze', 'ingest'];
                                                        const stageLabels: Record<string, string> = { upload: 'Upload', extract: 'Extract', analyze: 'Analyze', ingest: 'Ingest' };
                                                        const currentIdx = pipelineStages.indexOf(processingStage);
                                                        const isComplete = processingStage === 'completed';
                                                        return pipelineStages.map((stage, i) => {
                                                            const isDone = isComplete || i < currentIdx;
                                                            const isActive = !isComplete && i === currentIdx;
                                                            const isPending = !isComplete && i > currentIdx;
                                                            return (
                                                                <div key={stage} className="flex items-center gap-1.5">
                                                                    <motion.div
                                                                        className={cn(
                                                                            "h-8 w-8 rounded-full flex items-center justify-center text-xs font-medium transition-colors",
                                                                            isDone && "bg-green-500 text-white",
                                                                            isActive && "bg-primary text-primary-foreground",
                                                                            isPending && "bg-muted text-muted-foreground"
                                                                        )}
                                                                        animate={isActive ? getStageAnimation(stage) : {}}
                                                                    >
                                                                        {getStageIcon(stage, isDone)}
                                                                    </motion.div>
                                                                    <span className={cn(
                                                                        "text-xs hidden sm:inline",
                                                                        isDone && "text-green-600 font-medium",
                                                                        isActive && "text-primary font-medium",
                                                                        isPending && "text-muted-foreground"
                                                                    )}>{stageLabels[stage]}</span>
                                                                    {i < 3 && <ChevronRight className={cn(
                                                                        "h-4 w-4",
                                                                        isDone ? "text-green-500" : "text-muted-foreground"
                                                                    )} />}
                                                                </div>
                                                            );
                                                        });
                                                    })()}
                                                </div>
                                                {/* Stage description */}
                                                {isProcessing && (
                                                    <motion.p
                                                        key={processingStage}
                                                        initial={{ opacity: 0 }}
                                                        animate={{ opacity: 1 }}
                                                        className="text-xs text-muted-foreground mt-2 text-center italic"
                                                    >
                                                        {getStageDescription(processingStage)}
                                                    </motion.p>
                                                )}
                                                {/* Overall progress bar */}
                                                {isProcessing && (
                                                    <div className="mt-3">
                                                        <Progress
                                                            value={(() => {
                                                                if (!receivedData.length) return 0;
                                                                const total = receivedData.reduce((sum: number, f: any) => sum + (f.processingProgress || 0), 0);
                                                                return Math.round(total / receivedData.length);
                                                            })()}
                                                            className="h-1.5"
                                                        />
                                                        <p className="text-xs text-muted-foreground mt-1">
                                                            {receivedData.filter((f: any) => f.status === 'completed').length} / {receivedData.length} files complete
                                                        </p>
                                                    </div>
                                                )}
                                            </motion.div>
                                        )}
                                    </AnimatePresence>
                                </ScrollArea>
                            </TabsContent>

                            {/* AI Chat Tab */}
                            <TabsContent value="chat" className="flex-1 overflow-hidden m-0 flex flex-col min-h-0">
                                <ScrollArea className="flex-1 p-4 min-h-0">
                                    {chatMessages.length === 0 ? (
                                        <div className="text-center py-12 text-muted-foreground">
                                            <Bot className="h-12 w-12 mx-auto mb-3 opacity-50" />
                                            <p className="font-medium">Start a conversation with the GDPR AI Agent</p>
                                            <p className="text-xs mt-1 max-w-sm mx-auto">
                                                Ask questions about this request, GDPR law, or get help drafting responses.
                                                The AI has access to files uploaded to this request.
                                            </p>
                                        </div>
                                    ) : (
                                        <div className="space-y-4">
                                            <AnimatePresence>
                                                {chatMessages.map((msg: any, idx: number) => {
                                                    const isUser = msg.role === 'user';
                                                    return (
                                                        <motion.div
                                                            key={idx}
                                                            initial={{ opacity: 0, y: 10 }}
                                                            animate={{ opacity: 1, y: 0 }}
                                                            className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}
                                                        >
                                                            <div className={cn(
                                                                "h-8 w-8 rounded-full flex items-center justify-center shrink-0",
                                                                isUser ? 'bg-zinc-200 dark:bg-zinc-700' : 'bg-indigo-100 dark:bg-indigo-900'
                                                            )}>
                                                                {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4 text-indigo-700 dark:text-indigo-300" />}
                                                            </div>
                                                            <div className={`flex-1 max-w-[85%] ${isUser ? 'text-right' : ''}`}>
                                                                <div className={cn(
                                                                    "inline-block p-3 rounded-lg",
                                                                    isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
                                                                )}>
                                                                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                                                                </div>
                                                                {msg.timestamp && (
                                                                    <p className="text-xs text-muted-foreground mt-1">
                                                                        {new Date(msg.timestamp).toLocaleTimeString()}
                                                                    </p>
                                                                )}
                                                            </div>
                                                        </motion.div>
                                                    );
                                                })}
                                            </AnimatePresence>
                                            {chatLoading && (
                                                <motion.div
                                                    initial={{ opacity: 0 }}
                                                    animate={{ opacity: 1 }}
                                                    className="flex gap-3"
                                                >
                                                    <div className="h-8 w-8 rounded-full flex items-center justify-center bg-indigo-100 dark:bg-indigo-900">
                                                        <Loader2 className="h-4 w-4 text-indigo-700 dark:text-indigo-300 animate-spin" />
                                                    </div>
                                                    <div className="bg-muted p-3 rounded-lg">
                                                        <p className="text-sm text-muted-foreground">AI is thinking...</p>
                                                    </div>
                                                </motion.div>
                                            )}
                                            <div ref={chatEndRef} />
                                        </div>
                                    )}
                                </ScrollArea>
                                <div className="p-4 border-t shrink-0">
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            placeholder="Ask the GDPR AI agent..."
                                            value={chatInput}
                                            onChange={(e) => setChatInput(e.target.value)}
                                            onKeyPress={(e) => e.key === 'Enter' && sendChatMessage()}
                                            disabled={chatLoading}
                                            className="flex-1 px-4 py-2.5 text-sm rounded-lg border border-input bg-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                        />
                                        <Button
                                            size="lg"
                                            disabled={chatLoading || !chatInput.trim()}
                                            onClick={sendChatMessage}
                                        >
                                            {chatLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                                        </Button>
                                    </div>
                                </div>
                            </TabsContent>

                            {/* Policy Tab */}
                            <TabsContent value="analysis" className="flex-1 overflow-hidden m-0">
                                <ScrollArea className="h-full p-4">
                                    {!analysis ? (
                                        <div className="text-center py-12 text-muted-foreground">
                                            <FileText className="h-10 w-10 mx-auto mb-3 opacity-50" />
                                            <p className="font-medium">No policy analysis</p>
                                            <p className="text-xs mt-1">Scan the company's privacy policy to generate a GDPR analysis</p>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="mt-4 gap-2"
                                                onClick={async () => {
                                                    toast.info('Scanning privacy policy...');
                                                    try {
                                                        const res = await fetch('/api/gdpr-agent/analyze-policy', {
                                                            method: 'POST',
                                                            headers: { 'Content-Type': 'application/json' },
                                                            body: JSON.stringify({
                                                                company_name: request.company_name,
                                                                domain: request.domain || request.company_name,
                                                                request_id: request.id,
                                                            }),
                                                        });
                                                        const data = await res.json();
                                                        if (data.analysis) {
                                                            setAnalysis(data.analysis);
                                                            toast.success('Policy analysis complete');
                                                        } else {
                                                            toast.error(data.error || 'Analysis failed');
                                                        }
                                                    } catch {
                                                        toast.error('Failed to scan privacy policy');
                                                    }
                                                }}
                                            >
                                                <Search className="h-3.5 w-3.5" />Scan Privacy Policy
                                            </Button>
                                        </div>
                                    ) : (
                                        <div className="space-y-6">
                                            {analysis.dpo_email && (
                                                <div className="p-4 rounded-lg border bg-muted/30">
                                                    <p className="text-xs font-medium text-muted-foreground uppercase mb-2">Data Protection Officer</p>
                                                    <div className="flex items-center gap-2">
                                                        <Mail className="h-4 w-4 text-primary" />
                                                        <span className="font-medium">{analysis.dpo_email}</span>
                                                    </div>
                                                </div>
                                            )}
                                            {analysis.data_collected?.length > 0 && (
                                                <div>
                                                    <p className="text-xs font-medium text-muted-foreground uppercase mb-2">Data Collected</p>
                                                    <div className="flex flex-wrap gap-1.5">
                                                        {analysis.data_collected.map((item: string, i: number) => (
                                                            <Badge key={i} variant="secondary">{item}</Badge>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                            {analysis.third_party_sharing?.length > 0 && (
                                                <div>
                                                    <p className="text-xs font-medium text-muted-foreground uppercase mb-2">Third Party Sharing</p>
                                                    <div className="flex flex-wrap gap-1.5">
                                                        {analysis.third_party_sharing.map((item: string, i: number) => (
                                                            <Badge key={i} variant="outline" className="text-orange-600 border-orange-200">
                                                                <AlertTriangle className="h-3 w-3 mr-1" />{item}
                                                            </Badge>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </ScrollArea>
                            </TabsContent>
                        </Tabs>
                    </div>
                </div>

                {/* Footer */}
                <div className="p-4 border-t flex justify-between bg-muted/30 shrink-0">
                    <Button variant="outline" size="sm" onClick={() => toast.info("Export started")}>
                        <Download className="mr-2 h-4 w-4" /> Export All
                    </Button>
                    {request.status !== 'completed' && (
                        <Button size="sm" onClick={() => toast.success("Marked complete")}>
                            <CheckCircle2 className="mr-2 h-4 w-4" /> Mark Complete
                        </Button>
                    )}
                </div>
            </DialogContent>
        </Dialog >
    );
}
