"use client";
import { useState, useRef } from "react";
import Link from "next/link";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
    FileText,
    MessageSquare,
    CheckCircle,
    Paperclip,
    Image as ImageIcon,
    X,
    File,
} from "lucide-react";
import { toast } from "sonner";

interface ReviewItem {
    id: string;
    type: 'email' | 'file' | 'action' | 'message' | 'data';
    title: string;
    description: string;
    date: string;
    data?: unknown;
    companyName?: string;
    requestId?: string;
}

interface Attachment {
    id: string;
    name: string;
    type: 'file' | 'image';
    size: number;
    preview?: string;
    file: File;
}

interface ReviewDetailModalProps {
    isOpen: boolean;
    onClose: () => void;
    item: ReviewItem | null;
}

export function ReviewDetailModal({ isOpen, onClose, item }: ReviewDetailModalProps) {
    const [replyText, setReplyText] = useState("");
    const [attachments, setAttachments] = useState<Attachment[]>([]);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const imageInputRef = useRef<HTMLInputElement>(null);

    if (!item) return null;

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files) return;

        const newAttachments: Attachment[] = [];

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const isImage = file.type.startsWith('image/');

            const attachment: Attachment = {
                id: `${Date.now()}-${i}`,
                name: file.name,
                type: isImage ? 'image' : 'file',
                size: file.size,
                file,
            };

            // Create preview for images
            if (isImage) {
                attachment.preview = URL.createObjectURL(file);
            }

            newAttachments.push(attachment);
        }

        setAttachments(prev => [...prev, ...newAttachments]);

        // Reset input
        if (e.target) {
            e.target.value = '';
        }
    };

    const removeAttachment = (id: string) => {
        setAttachments(prev => {
            const attachment = prev.find(a => a.id === id);
            if (attachment?.preview) {
                URL.revokeObjectURL(attachment.preview);
            }
            return prev.filter(a => a.id !== id);
        });
    };

    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    const handleSendReply = () => {
        if (!replyText.trim() && attachments.length === 0) {
            toast.error("Please enter a message or attach files");
            return;
        }

        // Here you would normally upload files and send the message
        toast.success("Response queued", {
            description: `Message with ${attachments.length} attachment(s) will be sent via the agent.`
        });

        // Clean up
        attachments.forEach(a => {
            if (a.preview) URL.revokeObjectURL(a.preview);
        });
        setReplyText("");
        setAttachments([]);
        onClose();
    };

    const handleClose = () => {
        // Clean up previews
        attachments.forEach(a => {
            if (a.preview) URL.revokeObjectURL(a.preview);
        });
        setAttachments([]);
        setReplyText("");
        onClose();
    };

    return (
        <Dialog open={isOpen} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-[750px] h-[85vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        {(item.type === 'email' || item.type === 'message') && <MessageSquare className="h-5 w-5 text-blue-500" />}
                        {(item.type === 'file' || item.type === 'data') && <FileText className="h-5 w-5 text-amber-500" />}
                        <span className="truncate">{item.title}</span>
                        {item.companyName && (
                            <Badge variant="outline" className="ml-2">{item.companyName}</Badge>
                        )}
                    </DialogTitle>
                </DialogHeader>

                <Tabs defaultValue="overview" className="flex-1 flex flex-col min-h-0">
                    <TabsList className="grid w-full grid-cols-3">
                        <TabsTrigger value="overview">Overview</TabsTrigger>
                        <TabsTrigger value="data">Data Viewer</TabsTrigger>
                        <TabsTrigger value="reply">Reply</TabsTrigger>
                    </TabsList>

                    <div className="flex-1 min-h-0 mt-4">
                        <TabsContent value="overview" className="h-full">
                            <ScrollArea className="h-full rounded-md border p-4">
                                <div className="space-y-4">
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Description</h4>
                                        <p className="mt-1 text-sm">{item.description}</p>
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Received</h4>
                                        <p className="mt-1 text-sm">{item.date}</p>
                                    </div>
                                    {item.requestId && (
                                        <Button variant="outline" size="sm" asChild>
                                            <Link href={`/dashboard/requests/${item.requestId}`}>
                                                Open request detail
                                            </Link>
                                        </Button>
                                    )}
                                    <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg">
                                        <h4 className="text-sm font-medium mb-2 text-blue-700 dark:text-blue-300">AI Analysis</h4>
                                        <p className="text-sm text-blue-600 dark:text-blue-400">
                                            The system detected potential action items in this update.
                                            Please review the attached data or respond to the sender.
                                        </p>
                                    </div>
                                </div>
                            </ScrollArea>
                        </TabsContent>

                        <TabsContent value="data" className="h-full">
                            <ScrollArea className="h-full rounded-md border bg-zinc-900 text-zinc-50 p-4 font-mono text-xs">
                                <pre>{JSON.stringify(item.data || { info: "No raw data attached" }, null, 2)}</pre>
                            </ScrollArea>
                        </TabsContent>

                        <TabsContent value="reply" className="h-full flex flex-col gap-4">
                            {/* Message Input */}
                            <div className="flex-1 min-h-0">
                                <Textarea
                                    placeholder="Type your response instructions for the AI agent...

The agent will use this to compose a response email to the company."
                                    className="h-full resize-none p-4"
                                    value={replyText}
                                    onChange={(e) => setReplyText(e.target.value)}
                                />
                            </div>

                            {/* Attachments Section */}
                            {attachments.length > 0 && (
                                <div className="border rounded-lg p-3 space-y-2">
                                    <h4 className="text-xs font-medium text-muted-foreground uppercase">
                                        Attachments ({attachments.length})
                                    </h4>
                                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                                        {attachments.map((attachment) => (
                                            <div
                                                key={attachment.id}
                                                className="relative group border rounded-lg p-2 bg-zinc-50 dark:bg-zinc-900"
                                            >
                                                {attachment.type === 'image' && attachment.preview ? (
                                                    <div className="aspect-video rounded overflow-hidden bg-zinc-200 dark:bg-zinc-800 mb-2">
                                                        <img
                                                            src={attachment.preview}
                                                            alt={attachment.name}
                                                            className="w-full h-full object-cover"
                                                        />
                                                    </div>
                                                ) : (
                                                    <div className="aspect-video rounded bg-zinc-200 dark:bg-zinc-800 mb-2 flex items-center justify-center">
                                                        <File className="h-8 w-8 text-muted-foreground" />
                                                    </div>
                                                )}
                                                <p className="text-xs font-medium truncate">{attachment.name}</p>
                                                <p className="text-[10px] text-muted-foreground">
                                                    {formatFileSize(attachment.size)}
                                                </p>

                                                {/* Remove Button */}
                                                <button
                                                    onClick={() => removeAttachment(attachment.id)}
                                                    className="absolute -top-1.5 -right-1.5 h-5 w-5 rounded-full bg-red-500 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                                                >
                                                    <X className="h-3 w-3" />
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Attachment Buttons */}
                            <div className="flex items-center gap-2">
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    className="hidden"
                                    multiple
                                    accept=".pdf,.doc,.docx,.txt,.csv,.xlsx"
                                    onChange={handleFileSelect}
                                />
                                <input
                                    ref={imageInputRef}
                                    type="file"
                                    className="hidden"
                                    multiple
                                    accept="image/*"
                                    onChange={handleFileSelect}
                                />

                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => fileInputRef.current?.click()}
                                >
                                    <Paperclip className="h-4 w-4 mr-2" />
                                    Attach File
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => imageInputRef.current?.click()}
                                >
                                    <ImageIcon className="h-4 w-4 mr-2" />
                                    Add Photo
                                </Button>

                                <div className="flex-1" />

                                <span className="text-xs text-muted-foreground">
                                    Max 10MB per file
                                </span>
                            </div>

                            <div className="text-xs text-muted-foreground bg-zinc-50 dark:bg-zinc-900 p-2 rounded">
                                💡 Tip: Attach ID documents or screenshots to verify your identity when requested by companies.
                            </div>
                        </TabsContent>
                    </div>
                </Tabs>

                <DialogFooter className="mt-4 gap-2">
                    <Button variant="outline" onClick={handleClose}>Close</Button>
                    <Button onClick={handleSendReply} className="gap-2">
                        <CheckCircle className="h-4 w-4" />
                        {attachments.length > 0 ? `Send with ${attachments.length} file(s)` : 'Mark Resolved'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
