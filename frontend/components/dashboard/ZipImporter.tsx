'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import JSZip from 'jszip';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import {
    Upload, FileArchive, File, FileText, Image, FileSpreadsheet,
    FileAudio, FileVideo, Loader2, X, Sparkles, CheckCircle2,
    AlertCircle, Clock, ArrowRight, Database, Brain, Eye,
    RefreshCw, FileCode, LayoutList, Pencil, Trash2, Check
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Processing stages with descriptions
const PROCESSING_STAGES = [
    { id: 'upload', label: 'Uploading', description: 'Saving files to server', icon: Upload },
    { id: 'extract', label: 'Extracting', description: 'Parsing ZIP contents', icon: FileArchive },
    { id: 'analyze', label: 'Analyzing', description: 'Detecting file types', icon: Eye },
    { id: 'transcribe', label: 'Transcribing', description: 'Converting audio/video to text', icon: FileAudio },
    { id: 'convert', label: 'Converting', description: 'Generating markdown', icon: FileText },
    { id: 'ingest', label: 'Ingesting', description: 'Adding to knowledge graph', icon: Database },
    { id: 'complete', label: 'Complete', description: 'All files processed', icon: CheckCircle2 },
] as const;

interface ProcessedFile {
    id?: string;
    name: string;
    type: string;
    size: number;
    category: 'pdf' | 'image' | 'spreadsheet' | 'audio' | 'video' | 'document' | 'data' | 'other';
    content?: ArrayBuffer;
    status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
    processingStage?: string;
    processingProgress?: number;
    extractedText?: string;
    markdownContent?: string;
    transcript?: string;
    aiSummary?: string;
    errorMessage?: string;
}

interface ProcessingLog {
    id: string;
    timestamp: Date;
    message: string;
    type: 'info' | 'success' | 'error' | 'progress';
    fileId?: string;
}

interface ZipImporterProps {
    requestId?: string;
    onComplete?: (files: ProcessedFile[]) => void;
}

export function ZipImporter({ requestId, onComplete }: ZipImporterProps) {
    const [files, setFiles] = useState<ProcessedFile[]>([]);
    const [isExtracting, setIsExtracting] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [currentStage, setCurrentStage] = useState<string>('');
    const [overallProgress, setOverallProgress] = useState(0);
    const [logs, setLogs] = useState<ProcessingLog[]>([]);
    const [selectedFile, setSelectedFile] = useState<ProcessedFile | null>(null);
    const [previewOpen, setPreviewOpen] = useState(false);
    const [zipFile, setZipFile] = useState<File | null>(null);
    const [activeTab, setActiveTab] = useState('files');
    const [editingFileIndex, setEditingFileIndex] = useState<number | null>(null);
    const [editingName, setEditingName] = useState('');
    const logEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll logs
    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    // Add log entry
    const addLog = useCallback((message: string, type: ProcessingLog['type'] = 'info', fileId?: string) => {
        setLogs(prev => [...prev, {
            id: `log-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            timestamp: new Date(),
            message,
            type,
            fileId,
        }]);
    }, []);

    // Get file category
    const categorizeFile = (filename: string): ProcessedFile['category'] => {
        const ext = filename.split('.').pop()?.toLowerCase() || '';
        if (['pdf'].includes(ext)) return 'pdf';
        if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico'].includes(ext)) return 'image';
        if (['xlsx', 'xls', 'csv', 'tsv', 'ods'].includes(ext)) return 'spreadsheet';
        if (['mp3', 'wav', 'ogg', 'm4a', 'flac', 'aac', 'opus', 'wma', 'ape'].includes(ext)) return 'audio';
        if (['mp4', 'avi', 'mkv', 'mov', 'webm', 'flv', 'wmv', 'mpeg', 'mpg', '3gp'].includes(ext)) return 'video';
        if (['doc', 'docx', 'txt', 'rtf', 'md', 'odt'].includes(ext)) return 'document';
        if (['json', 'xml', 'html', 'htm', 'yaml', 'yml'].includes(ext)) return 'data';
        return 'other';
    };

    // Get file icon
    const getFileIcon = (category: ProcessedFile['category']) => {
        const icons = {
            pdf: <FileText className="h-4 w-4 text-red-500" />,
            image: <Image className="h-4 w-4 text-blue-500" />,
            spreadsheet: <FileSpreadsheet className="h-4 w-4 text-green-500" />,
            audio: <FileAudio className="h-4 w-4 text-purple-500" />,
            video: <FileVideo className="h-4 w-4 text-pink-500" />,
            document: <FileText className="h-4 w-4 text-zinc-500" />,
            data: <FileCode className="h-4 w-4 text-orange-500" />,
            other: <File className="h-4 w-4 text-zinc-400" />,
        };
        return icons[category];
    };

    // Get status icon
    const getStatusIcon = (status: ProcessedFile['status']) => {
        switch (status) {
            case 'pending':
                return <Clock className="h-3.5 w-3.5 text-zinc-400" />;
            case 'uploading':
            case 'processing':
                return <Loader2 className="h-3.5 w-3.5 text-blue-500 animate-spin" />;
            case 'completed':
                return <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />;
            case 'error':
                return <AlertCircle className="h-3.5 w-3.5 text-red-500" />;
        }
    };

    // Get MIME type
    const getMimeType = (filename: string): string => {
        const ext = filename.split('.').pop()?.toLowerCase() || '';
        const mimeTypes: Record<string, string> = {
            pdf: 'application/pdf',
            jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', gif: 'image/gif',
            csv: 'text/csv', tsv: 'text/tab-separated-values',
            xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            xls: 'application/vnd.ms-excel',
            txt: 'text/plain', json: 'application/json', xml: 'application/xml',
            mp3: 'audio/mpeg', wav: 'audio/wav', m4a: 'audio/mp4', flac: 'audio/flac',
            opus: 'audio/opus', ogg: 'audio/ogg', wma: 'audio/x-ms-wma',
            mp4: 'video/mp4', webm: 'video/webm', avi: 'video/x-msvideo',
            mov: 'video/quicktime', mkv: 'video/x-matroska', flv: 'video/x-flv',
            wmv: 'video/x-ms-wmv', mpeg: 'video/mpeg', '3gp': 'video/3gpp',
        };
        return mimeTypes[ext] || 'application/octet-stream';
    };

    // Format file size
    const formatSize = (bytes: number): string => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    // Handle file drop
    const onDrop = useCallback(async (acceptedFiles: File[]) => {
        const file = acceptedFiles[0];
        if (!file || !file.name.endsWith('.zip')) {
            toast.error('Please upload a ZIP file');
            return;
        }

        setZipFile(file);
        setIsExtracting(true);
        setCurrentStage('extract');
        setLogs([]);
        addLog(`Starting extraction of ${file.name}`, 'info');
        addLog(`ZIP file size: ${formatSize(file.size)}`, 'info');

        try {
            const zip = new JSZip();
            const contents = await zip.loadAsync(file);

            addLog(`ZIP opened successfully`, 'success');

            const extractedFiles: ProcessedFile[] = [];
            const filePromises: Promise<void>[] = [];
            let fileCount = 0;
            const totalFiles = Object.keys(contents.files).filter(k => !contents.files[k].dir).length;

            addLog(`Found ${totalFiles} files to extract`, 'info');

            contents.forEach((relativePath, zipEntry) => {
                if (!zipEntry.dir) {
                    const promise = zipEntry.async('arraybuffer').then((content) => {
                        fileCount++;
                        const category = categorizeFile(relativePath);
                        extractedFiles.push({
                            name: relativePath,
                            type: getMimeType(relativePath),
                            size: content.byteLength,
                            category,
                            content,
                            status: 'pending',
                        });
                        addLog(`Extracted: ${relativePath} (${formatSize(content.byteLength)}) [${category}]`, 'progress');
                        setOverallProgress(Math.round((fileCount / totalFiles) * 30));
                    });
                    filePromises.push(promise);
                }
            });

            await Promise.all(filePromises);

            // Sort by category for better organization
            extractedFiles.sort((a, b) => a.category.localeCompare(b.category));

            setFiles(extractedFiles);
            setCurrentStage('analyze');
            addLog(`Extraction complete! ${extractedFiles.length} files ready for processing`, 'success');

            // Log file type summary
            const summary = extractedFiles.reduce((acc, f) => {
                acc[f.category] = (acc[f.category] || 0) + 1;
                return acc;
            }, {} as Record<string, number>);

            addLog(`File types: ${Object.entries(summary).map(([k, v]) => `${v} ${k}`).join(', ')}`, 'info');

            toast.success(`Extracted ${extractedFiles.length} files from ZIP`);
        } catch (error) {
            console.error('Failed to extract ZIP:', error);
            addLog(`Error: ${error}`, 'error');
            toast.error('Failed to extract ZIP file');
        } finally {
            setIsExtracting(false);
            setOverallProgress(30);
        }
    }, [addLog]);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: { 'application/zip': ['.zip'] },
        maxFiles: 1,
        disabled: isExtracting || isProcessing,
    });

    // Process all files
    const handleProcess = async () => {
        setIsProcessing(true);
        setCurrentStage('upload');
        setOverallProgress(30);

        try {
            addLog('Starting file upload to server...', 'info');

            // Step 1: Upload files to server
            const formData = new FormData();
            if (requestId) formData.append('requestId', requestId);
            if (zipFile) formData.append('sourceZip', zipFile.name);

            // Convert ArrayBuffer content to Blobs for upload
            for (const file of files) {
                if (file.content) {
                    const blob = new Blob([file.content], { type: file.type });
                    formData.append('files', blob, file.name);
                }
            }

            const uploadRes = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
            });

            if (!uploadRes.ok) {
                throw new Error('Upload failed');
            }

            const uploadData = await uploadRes.json();
            addLog(`Uploaded ${uploadData.files.length} files (${uploadData.totalSizeMb} MB)`, 'success');
            setOverallProgress(40);

            // Update files with server IDs
            const updatedFiles = files.map(f => {
                const serverFile = uploadData.files.find((sf: { fileName: string }) =>
                    sf.fileName.includes(f.name.split('/').pop() || f.name)
                );
                return {
                    ...f,
                    id: serverFile?.id,
                    status: 'pending' as const,
                };
            });
            setFiles(updatedFiles);

            // Step 2: Process each file
            setCurrentStage('transcribe');
            addLog('Starting AI processing...', 'info');

            const totalFiles = updatedFiles.length;
            let processedCount = 0;

            for (const file of updatedFiles) {
                if (!file.id) continue;

                const category = file.category;
                const stage = category === 'audio' || category === 'video' ? 'transcribe' :
                    category === 'spreadsheet' ? 'parse' :
                        category === 'image' ? 'ocr' : 'extract';

                addLog(`Processing: ${file.name} (${stage})`, 'progress', file.id);

                // Update UI
                setFiles(prev => prev.map(f =>
                    f.id === file.id ? { ...f, status: 'processing', processingStage: stage } : f
                ));

                // Call process API
                try {
                    const processRes = await fetch('/api/upload/process', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ fileId: file.id, action: category }),
                    });

                    const result = await processRes.json();

                    if (result.success) {
                        addLog(`✓ Completed: ${file.name}`, 'success', file.id);
                        setFiles(prev => prev.map(f =>
                            f.id === file.id ? {
                                ...f,
                                status: 'completed',
                                processingStage: 'complete',
                                processingProgress: 100,
                                markdownContent: result.content,
                            } : f
                        ));
                    } else {
                        throw new Error(result.error || 'Processing failed');
                    }
                } catch (err) {
                    addLog(`✗ Error: ${file.name} - ${err}`, 'error', file.id);
                    setFiles(prev => prev.map(f =>
                        f.id === file.id ? {
                            ...f,
                            status: 'error',
                            errorMessage: String(err),
                        } : f
                    ));
                }

                processedCount++;
                setOverallProgress(40 + Math.round((processedCount / totalFiles) * 50));
            }

            // Step 3: Graph ingestion
            setCurrentStage('ingest');
            addLog('Adding data to knowledge graph...', 'info');
            setOverallProgress(95);

            // Trigger graph ingestion for completed files
            const completedFiles = files.filter(f => f.status === 'completed' && f.id);
            let ingestedCount = 0;

            for (const file of completedFiles) {
                if (!file.id) continue;

                try {
                    const ingestRes = await fetch('/api/upload/process', {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ fileId: file.id }),
                    });

                    const result = await ingestRes.json();

                    if (result.success) {
                        ingestedCount++;
                        addLog(`✓ Ingested to graph: ${file.name}`, 'success', file.id);
                    } else {
                        addLog(`⚠ Skipped graph ingestion: ${file.name}`, 'progress', file.id);
                    }
                } catch (err) {
                    addLog(`⚠ Graph ingestion failed: ${file.name}`, 'error', file.id);
                }
            }

            addLog(`Knowledge graph updated with ${ingestedCount} files`, 'success');

            // Complete
            setCurrentStage('complete');
            setOverallProgress(100);
            addLog('All processing complete!', 'success');

            toast.success('Files processed successfully', {
                description: `${processedCount} files analyzed and ${ingestedCount} added to knowledge graph`
            });

            onComplete?.(files.filter(f => f.status === 'completed'));
        } catch (error) {
            console.error('Processing failed:', error);
            addLog(`Fatal error: ${error}`, 'error');
            toast.error('Failed to process files');
        } finally {
            setIsProcessing(false);
        }
    };

    // Clear all files
    const handleClear = () => {
        setFiles([]);
        setZipFile(null);
        setLogs([]);
        setOverallProgress(0);
        setCurrentStage('');
    };

    // Open preview dialog
    const handlePreview = async (file: ProcessedFile) => {
        if (!file.id) return;

        // Fetch latest file data
        const res = await fetch(`/api/upload?fileId=${file.id}`);
        const data = await res.json();

        if (data.success && data.files.length > 0) {
            setSelectedFile({
                ...file,
                markdownContent: data.files[0].markdownContent,
                transcript: data.files[0].transcript,
                aiSummary: data.files[0].aiSummary,
                extractedText: data.files[0].extractedText,
            });
            setPreviewOpen(true);
        }
    };

    // Rename a file in the local list
    const handleRenameFile = (index: number, newName: string) => {
        setFiles(prev => prev.map((f, i) => i === index ? { ...f, name: newName } : f));
        setEditingFileIndex(null);
        setEditingName('');
    };

    // Remove a file from the local list (only pending/error)
    const handleRemoveFile = (index: number) => {
        setFiles(prev => prev.filter((_, i) => i !== index));
        addLog(`Removed file: ${files[index]?.name}`, 'info');
    };

    // Get category counts
    const categoryCounts = files.reduce((acc, f) => {
        acc[f.category] = (acc[f.category] || 0) + 1;
        return acc;
    }, {} as Record<string, number>);

    return (
        <Card className="w-full">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="text-lg font-semibold flex items-center gap-2">
                            <FileArchive className="h-5 w-5 text-indigo-500" />
                            GDPR Data Import
                        </CardTitle>
                        <CardDescription>
                            Upload a ZIP file from your GDPR data request
                        </CardDescription>
                    </div>
                    {files.length > 0 && (
                        <Button variant="outline" size="sm" onClick={handleClear}>
                            <X className="h-4 w-4 mr-1" />
                            Clear
                        </Button>
                    )}
                </div>
            </CardHeader>

            <CardContent className="space-y-4">
                {/* Dropzone */}
                {files.length === 0 && (
                    <div
                        {...getRootProps()}
                        className={cn(
                            'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all',
                            isDragActive ? 'border-primary bg-primary/5 scale-[1.02]' : 'border-muted-foreground/25 hover:border-primary/50',
                            (isExtracting || isProcessing) && 'opacity-50 cursor-not-allowed'
                        )}
                    >
                        <input {...getInputProps()} />
                        {isExtracting ? (
                            <>
                                <Loader2 className="h-10 w-10 mx-auto mb-3 animate-spin text-primary" />
                                <p className="text-sm font-medium">Extracting ZIP contents...</p>
                            </>
                        ) : (
                            <>
                                <Upload className="h-10 w-10 mx-auto mb-3 text-muted-foreground" />
                                <p className="text-sm font-medium">
                                    {isDragActive ? 'Drop ZIP file here' : 'Drag & drop a ZIP file, or click to browse'}
                                </p>
                                <p className="text-xs text-muted-foreground mt-2">
                                    Supports PDFs, images, spreadsheets, audio, video, and documents
                                </p>
                            </>
                        )}
                    </div>
                )}

                {/* Processing Pipeline Visualization */}
                {(isExtracting || isProcessing || currentStage) && (
                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-medium">Processing Pipeline</span>
                            <span className="text-sm text-muted-foreground">{overallProgress}%</span>
                        </div>
                        <Progress value={overallProgress} className="h-2" />
                        <div className="flex items-center gap-1 overflow-x-auto pb-2">
                            {PROCESSING_STAGES.map((stage, idx) => {
                                const isActive = currentStage === stage.id;
                                const isPast = PROCESSING_STAGES.findIndex(s => s.id === currentStage) > idx;
                                const Icon = stage.icon;

                                return (
                                    <div key={stage.id} className="flex items-center flex-shrink-0">
                                        <div
                                            className={cn(
                                                'flex items-center gap-1.5 px-2 py-1 rounded-full text-xs transition-all',
                                                isActive && 'bg-primary text-primary-foreground',
                                                isPast && 'bg-green-500/10 text-green-600',
                                                !isActive && !isPast && 'bg-muted text-muted-foreground'
                                            )}
                                        >
                                            {isActive ? (
                                                <Loader2 className="h-3 w-3 animate-spin" />
                                            ) : isPast ? (
                                                <CheckCircle2 className="h-3 w-3" />
                                            ) : (
                                                <Icon className="h-3 w-3" />
                                            )}
                                            <span className="hidden sm:inline">{stage.label}</span>
                                        </div>
                                        {idx < PROCESSING_STAGES.length - 1 && (
                                            <ArrowRight className="h-3 w-3 text-muted-foreground mx-0.5" />
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Process Button — placed above file list so it's always accessible */}
                {files.length > 0 && !isProcessing && currentStage !== 'complete' && (
                    <Button onClick={handleProcess} className="w-full" size="lg">
                        <Sparkles className="mr-2 h-4 w-4" />
                        Process {files.length} Files with AI
                    </Button>
                )}

                {/* Files and Logs Tabs */}
                {files.length > 0 && (
                    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                        <TabsList className="w-full grid grid-cols-2">
                            <TabsTrigger value="files" className="gap-1.5">
                                <LayoutList className="h-3.5 w-3.5" />
                                Files ({files.length})
                            </TabsTrigger>
                            <TabsTrigger value="logs" className="gap-1.5">
                                <FileCode className="h-3.5 w-3.5" />
                                Logs ({logs.length})
                            </TabsTrigger>
                        </TabsList>

                        <TabsContent value="files" className="mt-3">
                            {/* File Type Summary */}
                            <div className="flex flex-wrap gap-2 mb-3">
                                {Object.entries(categoryCounts).map(([cat, count]) => (
                                    <Badge key={cat} variant="secondary" className="text-xs">
                                        {getFileIcon(cat as ProcessedFile['category'])}
                                        <span className="ml-1">{count} {cat}</span>
                                    </Badge>
                                ))}
                            </div>

                            {/* File List */}
                            <ScrollArea className="h-[50vh]">
                                <div className="space-y-1 pr-3">
                                    {files.map((file, i) => (
                                        <div
                                            key={i}
                                            className={cn(
                                                'flex items-center gap-2 p-2 rounded-lg text-sm transition-colors',
                                                file.status === 'processing' && 'bg-blue-50 dark:bg-blue-900/20',
                                                file.status === 'completed' && 'bg-green-50 dark:bg-green-900/20',
                                                file.status === 'error' && 'bg-red-50 dark:bg-red-900/20',
                                                file.status === 'pending' && 'bg-muted/50'
                                            )}
                                        >
                                            {getFileIcon(file.category)}

                                            {/* Inline editable file name */}
                                            {editingFileIndex === i ? (
                                                <div className="flex-1 flex items-center gap-1">
                                                    <input
                                                        type="text"
                                                        value={editingName}
                                                        onChange={(e) => setEditingName(e.target.value)}
                                                        onKeyDown={(e) => {
                                                            if (e.key === 'Enter') handleRenameFile(i, editingName);
                                                            if (e.key === 'Escape') { setEditingFileIndex(null); setEditingName(''); }
                                                        }}
                                                        className="flex-1 text-xs font-mono bg-background border rounded px-1.5 py-0.5 outline-none focus:ring-1 focus:ring-primary"
                                                        autoFocus
                                                    />
                                                    <Button variant="ghost" size="icon" className="h-5 w-5" onClick={() => handleRenameFile(i, editingName)}>
                                                        <Check className="h-3 w-3 text-green-600" />
                                                    </Button>
                                                    <Button variant="ghost" size="icon" className="h-5 w-5" onClick={() => { setEditingFileIndex(null); setEditingName(''); }}>
                                                        <X className="h-3 w-3" />
                                                    </Button>
                                                </div>
                                            ) : (
                                                <span className="flex-1 truncate font-mono text-xs">{file.name}</span>
                                            )}

                                            <span className="text-xs text-muted-foreground">{formatSize(file.size)}</span>

                                            {/* Granular per-file processing stage badge */}
                                            {file.processingStage && file.status === 'processing' && (
                                                <Badge variant="outline" className="text-xs gap-1 animate-pulse">
                                                    <Loader2 className="h-2.5 w-2.5 animate-spin" />
                                                    {file.processingStage}
                                                </Badge>
                                            )}
                                            {file.status === 'error' && file.errorMessage && (
                                                <span className="text-xs text-red-500 max-w-[120px] truncate" title={file.errorMessage}>
                                                    {file.errorMessage}
                                                </span>
                                            )}

                                            {getStatusIcon(file.status)}

                                            {/* Preview button */}
                                            {file.status === 'completed' && file.id && (
                                                <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => handlePreview(file)} title="Preview">
                                                    <Eye className="h-3 w-3" />
                                                </Button>
                                            )}

                                            {/* Rename button (not during processing) */}
                                            {file.status !== 'processing' && editingFileIndex !== i && (
                                                <Button
                                                    variant="ghost" size="icon" className="h-6 w-6"
                                                    onClick={() => { setEditingFileIndex(i); setEditingName(file.name); }}
                                                    title="Rename"
                                                >
                                                    <Pencil className="h-3 w-3" />
                                                </Button>
                                            )}

                                            {/* Remove button (only pending/error) */}
                                            {(file.status === 'pending' || file.status === 'error') && (
                                                <Button
                                                    variant="ghost" size="icon" className="h-6 w-6 text-red-500 hover:text-red-700"
                                                    onClick={() => handleRemoveFile(i)}
                                                    title="Remove"
                                                >
                                                    <Trash2 className="h-3 w-3" />
                                                </Button>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </ScrollArea>
                        </TabsContent>

                        <TabsContent value="logs" className="mt-3">
                            <ScrollArea className="h-64 bg-zinc-950 rounded-lg p-3 font-mono text-xs">
                                <div className="space-y-1">
                                    {logs.map((log) => (
                                        <div
                                            key={log.id}
                                            className={cn(
                                                'flex gap-2',
                                                log.type === 'success' && 'text-green-400',
                                                log.type === 'error' && 'text-red-400',
                                                log.type === 'progress' && 'text-zinc-400',
                                                log.type === 'info' && 'text-blue-400'
                                            )}
                                        >
                                            <span className="text-zinc-600 flex-shrink-0">
                                                [{log.timestamp.toLocaleTimeString()}]
                                            </span>
                                            <span>{log.message}</span>
                                        </div>
                                    ))}
                                    <div ref={logEndRef} />
                                </div>
                            </ScrollArea>
                        </TabsContent>
                    </Tabs>
                )}

                {/* Process button moved above file tabs for visibility */}

                {/* Completion State */}
                {currentStage === 'complete' && (
                    <div className="flex items-center justify-center gap-2 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                        <span className="text-green-700 font-medium">All files processed successfully!</span>
                    </div>
                )}

                {/* Preview Dialog */}
                <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
                    <DialogContent className="max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                {selectedFile && getFileIcon(selectedFile.category)}
                                {selectedFile?.name}
                            </DialogTitle>
                            <DialogDescription>
                                {selectedFile?.aiSummary && (
                                    <div className="mt-2 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg text-sm">
                                        <div className="flex items-center gap-1.5 mb-1 font-medium text-amber-700">
                                            <Brain className="h-3.5 w-3.5" />
                                            AI Summary
                                        </div>
                                        <div className="text-amber-800 dark:text-amber-200 prose prose-sm prose-amber dark:prose-invert max-w-none">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                {selectedFile.aiSummary}
                                            </ReactMarkdown>
                                        </div>
                                    </div>
                                )}
                            </DialogDescription>
                        </DialogHeader>
                        <ScrollArea className="flex-1 mt-4">
                            <div className="prose prose-sm dark:prose-invert max-w-none p-4">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {selectedFile?.markdownContent || selectedFile?.transcript || selectedFile?.extractedText || '*No content available*'}
                                </ReactMarkdown>
                            </div>
                        </ScrollArea>
                    </DialogContent>
                </Dialog>
            </CardContent>
        </Card>
    );
}
