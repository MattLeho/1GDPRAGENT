'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Shield, Upload, Eye, EyeOff, Trash2, FileText, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';

interface IDDocument {
    id: number;
    documentType: 'passport' | 'drivers_license' | 'national_id' | 'utility_bill';
    fileName: string;
    fileUrl: string;
    censoredUrl?: string;
    uploadedAt: Date;
}

const DOCUMENT_TYPES = [
    { value: 'passport', label: 'Passport' },
    { value: 'drivers_license', label: "Driver's License" },
    { value: 'national_id', label: 'National ID' },
    { value: 'utility_bill', label: 'Utility Bill' },
];

export function IDDocumentsSection() {
    const [documents, setDocuments] = useState<IDDocument[]>([]);
    const [selectedType, setSelectedType] = useState<string>('passport');
    const [isUploading, setIsUploading] = useState(false);
    const [viewMode, setViewMode] = useState<Record<number, 'censored' | 'uncensored'>>({});

    // Load documents on mount
    useEffect(() => {
        loadDocuments();
    }, []);

    const loadDocuments = async () => {
        try {
            const res = await fetch('/api/settings/id-documents');
            if (res.ok) {
                const data = await res.json();
                if (data.documents) {
                    setDocuments(data.documents);
                    // Initialize all to censored view
                    const initial: Record<number, 'censored' | 'uncensored'> = {};
                    data.documents.forEach((doc: IDDocument) => {
                        initial[doc.id] = 'censored';
                    });
                    setViewMode(initial);
                }
            }
        } catch (error) {
            console.error('Failed to load documents:', error);
        }
    };

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        // Validate file type
        const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf'];
        if (!validTypes.includes(file.type)) {
            toast.error('Please upload an image (JPG, PNG, GIF, WebP) or PDF');
            return;
        }

        // Validate file size (max 10MB)
        if (file.size > 10 * 1024 * 1024) {
            toast.error('File must be less than 10MB');
            return;
        }

        setIsUploading(true);
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('documentType', selectedType);

            const res = await fetch('/api/settings/id-documents', {
                method: 'POST',
                body: formData,
            });

            const data = await res.json();

            if (data.success) {
                toast.success('Document uploaded and processed');
                loadDocuments(); // Reload list
            } else {
                toast.error(data.error || 'Failed to upload document');
            }
        } catch (error) {
            toast.error('Failed to upload document');
        } finally {
            setIsUploading(false);
            e.target.value = ''; // Reset input
        }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('Are you sure you want to delete this document?')) {
            return;
        }

        try {
            const res = await fetch(`/api/settings/id-documents?id=${id}`, {
                method: 'DELETE',
            });

            const data = await res.json();

            if (data.success) {
                toast.success('Document deleted');
                setDocuments(documents.filter(d => d.id !== id));
            } else {
                toast.error(data.error || 'Failed to delete document');
            }
        } catch (error) {
            toast.error('Failed to delete document');
        }
    };

    const toggleViewMode = (id: number) => {
        setViewMode({
            ...viewMode,
            [id]: viewMode[id] === 'censored' ? 'uncensored' : 'censored',
        });
    };

    const getDocumentLabel = (type: string) => {
        return DOCUMENT_TYPES.find(t => t.value === type)?.label || type;
    };

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center gap-2">
                    <Shield className="h-5 w-5 text-emerald-500" />
                    <CardTitle>ID Documents</CardTitle>
                </div>
                <CardDescription>
                    Upload identity documents with automatic redaction for sensitive information
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Upload Section */}
                <div className="rounded-lg border-2 border-dashed border-zinc-200 dark:border-zinc-800 p-6">
                    <div className="flex flex-col items-center gap-4">
                        <div className="h-12 w-12 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
                            <FileText className="h-6 w-6 text-emerald-600" />
                        </div>
                        <div className="text-center">
                            <h4 className="font-medium mb-1">Upload ID Document</h4>
                            <p className="text-sm text-muted-foreground mb-4">
                                Select document type and upload. Sensitive info will be auto-redacted.
                            </p>
                        </div>
                        <div className="flex items-center gap-2 w-full max-w-md">
                            <Select value={selectedType} onValueChange={setSelectedType}>
                                <SelectTrigger className="flex-1">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {DOCUMENT_TYPES.map((type) => (
                                        <SelectItem key={type.value} value={type.value}>
                                            {type.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <Label htmlFor="id-upload" className="cursor-pointer">
                                <Button
                                    type="button"
                                    disabled={isUploading}
                                    onClick={() => document.getElementById('id-upload')?.click()}
                                >
                                    {isUploading ? (
                                        <>
                                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                            Processing...
                                        </>
                                    ) : (
                                        <>
                                            <Upload className="mr-2 h-4 w-4" />
                                            Upload
                                        </>
                                    )}
                                </Button>
                            </Label>
                            <input
                                id="id-upload"
                                type="file"
                                accept="image/*,application/pdf"
                                className="hidden"
                                onChange={handleUpload}
                                disabled={isUploading}
                            />
                        </div>
                    </div>
                </div>

                {/* Documents List */}
                {documents.length > 0 ? (
                    <div className="space-y-3">
                        <Label className="text-sm font-medium">Uploaded Documents</Label>
                        {documents.map((doc) => (
                            <div
                                key={doc.id}
                                className="rounded-lg border p-4 space-y-3"
                            >
                                <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h5 className="font-medium text-sm">
                                                {getDocumentLabel(doc.documentType)}
                                            </h5>
                                            <Badge variant="secondary" className="text-xs">
                                                {viewMode[doc.id] === 'censored' ? 'Censored' : 'Uncensored'}
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-muted-foreground">
                                            {doc.fileName} • {new Date(doc.uploadedAt).toLocaleDateString()}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-1">
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            onClick={() => toggleViewMode(doc.id)}
                                            title={viewMode[doc.id] === 'censored' ? 'Show uncensored' : 'Show censored'}
                                        >
                                            {viewMode[doc.id] === 'censored' ? (
                                                <Eye className="h-4 w-4" />
                                            ) : (
                                                <EyeOff className="h-4 w-4" />
                                            )}
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            onClick={() => handleDelete(doc.id)}
                                            className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    </div>
                                </div>

                                {/* Document Preview */}
                                <div className="rounded-md overflow-hidden border bg-zinc-50 dark:bg-zinc-900">
                                    <img
                                        src={viewMode[doc.id] === 'censored' ? (doc.censoredUrl || doc.fileUrl) : doc.fileUrl}
                                        alt={`${getDocumentLabel(doc.documentType)} preview`}
                                        className="w-full h-auto max-h-64 object-contain"
                                    />
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-center py-8 text-sm text-muted-foreground">
                        No documents uploaded yet
                    </div>
                )}

                {/* Privacy Notice */}
                <div className="rounded-md bg-blue-50 dark:bg-blue-950/30 p-3 text-xs text-blue-700 dark:text-blue-400">
                    <Shield className="h-3.5 w-3.5 inline mr-1" />
                    Your documents are encrypted and stored locally. Sensitive information (ID numbers, addresses, etc.) is automatically redacted in the censored version.
                </div>
            </CardContent>
        </Card>
    );
}
