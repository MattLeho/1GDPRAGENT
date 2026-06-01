'use client';

/**
 * Animated File Processing Card
 * Shows real-time per-file processing with professional, clean animations
 * No emojis - uses lucide icons and tailwind animations
 */

import { motion } from 'framer-motion';
import {
    FileText, Image, FileSpreadsheet, FileAudio, FileVideo, File, FileCode,
    Upload, Eye, FileArchive, Database, Sparkles, CheckCircle2, AlertCircle,
    Loader2, ArrowRight
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

interface ProcessingStage {
    id: string;
    label: string;
    description: string;
}

const STAGES: ProcessingStage[] = [
    { id: 'upload', label: 'Upload', description: 'Saving to server' },
    { id: 'extract', label: 'Extract', description: 'Reading content' },
    { id: 'transcribe', label: 'Transcribe', description: 'Audio to text' },
    { id: 'convert', label: 'Convert', description: 'To markdown' },
    { id: 'summarize', label: 'Summarize', description: 'AI analysis' },
    { id: 'ingest', label: 'Ingest', description: 'To knowledge graph' },
];

interface FileCardProps {
    file: {
        name: string;
        type: string;
        size: number;
        category: 'pdf' | 'image' | 'spreadsheet' | 'audio' | 'video' | 'document' | 'data' | 'other';
        status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
        processingStage?: string;
        processingProgress?: number;
        errorMessage?: string;
    };
    onRemove?: () => void;
}

export function FileProcessingCard({ file, onRemove }: FileCardProps) {
    const getFileIcon = () => {
        const iconClass = "h-5 w-5";
        switch (file.category) {
            case 'pdf': return <FileText className={cn(iconClass, "text-red-500")} />;
            case 'image': return <Image className={cn(iconClass, "text-blue-500")} />;
            case 'spreadsheet': return <FileSpreadsheet className={cn(iconClass, "text-green-500")} />;
            case 'audio': return <FileAudio className={cn(iconClass, "text-purple-500")} />;
            case 'video': return <FileVideo className={cn(iconClass, "text-pink-500")} />;
            case 'data': return <FileCode className={cn(iconClass, "text-orange-500")} />;
            default: return <File className={cn(iconClass, "text-zinc-500")} />;
        }
    };

    const getStageIcon = (stageId: string) => {
        const iconClass = "h-4 w-4";
        switch (stageId) {
            case 'upload': return <Upload className={iconClass} />;
            case 'extract': return <FileArchive className={iconClass} />;
            case 'transcribe': return <FileAudio className={iconClass} />;
            case 'convert': return <FileText className={iconClass} />;
            case 'summarize': return <Sparkles className={iconClass} />;
            case 'ingest': return <Database className={iconClass} />;
            default: return <Eye className={iconClass} />;
        }
    };

    const getStatusBadge = () => {
        switch (file.status) {
            case 'pending':
                return <Badge variant="outline" className="text-zinc-500">Pending</Badge>;
            case 'uploading':
            case 'processing':
                return (
                    <Badge variant="outline" className="text-blue-500 border-blue-500">
                        <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        Processing
                    </Badge>
                );
            case 'completed':
                return (
                    <Badge className="bg-green-500 text-white">
                        <CheckCircle2 className="h-3 w-3 mr-1" />
                        Complete
                    </Badge>
                );
            case 'error':
                return (
                    <Badge variant="destructive">
                        <AlertCircle className="h-3 w-3 mr-1" />
                        Error
                    </Badge>
                );
        }
    };

    const formatSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    const currentStageIndex = file.processingStage
        ? STAGES.findIndex(s => s.id === file.processingStage)
        : -1;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className={cn(
                "group relative p-4 border rounded-lg transition-all",
                file.status === 'error' ? "border-red-300 bg-red-50 dark:bg-red-950/20" :
                    file.status === 'completed' ? "border-green-300 bg-green-50 dark:bg-green-950/20" :
                        file.status === 'processing' ? "border-blue-300 bg-blue-50 dark:bg-blue-950/20" :
                            "border-zinc-200 bg-white dark:bg-zinc-900 dark:border-zinc-800"
            )}
        >
            {/* Header */}
            <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                    <motion.div
                        animate={file.status === 'processing' ? {
                            scale: [1, 1.1, 1],
                            rotate: [0, 5, -5, 0]
                        } : {}}
                        transition={{ duration: 2, repeat: Infinity }}
                    >
                        {getFileIcon()}
                    </motion.div>
                    <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">{file.name}</p>
                        <p className="text-xs text-zinc-500">{formatSize(file.size)}</p>
                    </div>
                </div>
                {getStatusBadge()}
            </div>

            {/* Processing Stages Timeline */}
            {(file.status === 'processing' || file.status === 'completed') && (
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        {STAGES.map((stage, index) => {
                            const isCompleted = index < currentStageIndex;
                            const isCurrent = index === currentStageIndex;
                            const isPending = index > currentStageIndex;

                            return (
                                <div key={stage.id} className="flex items-center">
                                    <motion.div
                                        initial={{ scale: 0 }}
                                        animate={{ scale: 1 }}
                                        transition={{ delay: index * 0.1 }}
                                        className={cn(
                                            "relative flex items-center justify-center h-8 w-8 rounded-full border-2",
                                            isCompleted && "border-green-500 bg-green-100 dark:bg-green-950",
                                            isCurrent && "border-blue-500 bg-blue-100 dark:bg-blue-950",
                                            isPending && "border-zinc-300 bg-zinc-100 dark:bg-zinc-800 dark:border-zinc-700"
                                        )}
                                    >
                                        {isCompleted ? (
                                            <CheckCircle2 className="h-4 w-4 text-green-600" />
                                        ) : isCurrent ? (
                                            <motion.div
                                                animate={{ rotate: 360 }}
                                                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                                            >
                                                {getStageIcon(stage.id)}
                                            </motion.div>
                                        ) : (
                                            <div className="h-2 w-2 rounded-full bg-zinc-300 dark:bg-zinc-600" />
                                        )}
                                    </motion.div>
                                    {index < STAGES.length - 1 && (
                                        <div className={cn(
                                            "h-0.5 w-8 mx-1",
                                            isCompleted ? "bg-green-500" : "bg-zinc-300 dark:bg-zinc-700"
                                        )} />
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {/* Current Stage Label */}
                    {file.processingStage && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-400"
                        >
                            <ArrowRight className="h-3 w-3" />
                            {STAGES.find(s => s.id === file.processingStage)?.description || 'Processing'}
                        </motion.div>
                    )}

                    {/* Progress Bar */}
                    {typeof file.processingProgress === 'number' && (
                        <div className="space-y-1">
                            <Progress value={file.processingProgress} className="h-1.5" />
                            <p className="text-xs text-right text-zinc-500">
                                {file.processingProgress}%
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* Error Message */}
            {file.status === 'error' && file.errorMessage && (
                <div className="mt-3 p-2 bg-red-100 dark:bg-red-950 rounded text-xs text-red-700 dark:text-red-300">
                    {file.errorMessage}
                </div>
            )}
        </motion.div>
    );
}
