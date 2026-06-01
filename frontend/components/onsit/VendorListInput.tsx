'use client';

/**
 * Vendor List Input Dialog
 * 
 * Allows users to input vendor lists from cookie consent dialogs via:
 * - Screenshot upload (OCR with Gemini Vision)
 * - Screen recording upload (frame extraction + OCR)
 * - Copy/paste text
 * 
 * Extracts vendor names and adds them to ONSIT discovery queue.
 */

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
    Upload,
    Image,
    Video,
    FileText,
    Sparkles,
    Loader2,
    X,
    CheckCircle2,
    ListPlus,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface VendorListInputProps {
    onVendorsExtracted?: (vendors: string[]) => void;
}

export function VendorListInput({ onVendorsExtracted }: VendorListInputProps) {
    const [open, setOpen] = useState(false);
    const [activeTab, setActiveTab] = useState('screenshot');
    const [processing, setProcessing] = useState(false);
    const [textInput, setTextInput] = useState('');
    const [imageFile, setImageFile] = useState<File | null>(null);
    const [videoFile, setVideoFile] = useState<File | null>(null);
    const [extractedVendors, setExtractedVendors] = useState<string[]>([]);
    const [previewUrl, setPreviewUrl] = useState<string>('');

    // Handle file selection
    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>, type: 'image' | 'video') => {
        const file = e.target.files?.[0];
        if (!file) return;

        if (type === 'image') {
            if (!file.type.startsWith('image/')) {
                toast.error('Please select an image file');
                return;
            }
            setImageFile(file);
        } else {
            if (!file.type.startsWith('video/')) {
                toast.error('Please select a video file');
                return;
            }
            setVideoFile(file);
        }

        // Create preview URL
        const url = URL.createObjectURL(file);
        setPreviewUrl(url);
    };

    // Process screenshot with OCR
    const handleProcessScreenshot = async () => {
        if (!imageFile) {
            toast.error('Please select an image first');
            return;
        }

        setProcessing(true);

        try {
            // Convert image to base64
            const reader = new FileReader();
            const base64Promise = new Promise<string>((resolve) => {
                reader.onload = () => resolve(reader.result as string);
                reader.readAsDataURL(imageFile);
            });

            const base64Image = await base64Promise;

            // Call API for OCR + vendor extraction
            const response = await fetch('/api/onsit/extract-vendors', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: 'image',
                    data: base64Image,
                }),
            });

            const result = await response.json();

            if (result.success && result.vendors) {
                setExtractedVendors(result.vendors);
                toast.success(`Extracted ${result.vendors.length} vendors`);
            } else {
                throw new Error(result.error || 'Failed to extract vendors');
            }
        } catch (error) {
            console.error('Screenshot processing failed:', error);
            toast.error('Failed to process screenshot');
        } finally {
            setProcessing(false);
        }
    };

    // Process screen recording
    const handleProcessVideo = async () => {
        if (!videoFile) {
            toast.error('Please select a video first');
            return;
        }

        setProcessing(true);

        try {
            const formData = new FormData();
            formData.append('video', videoFile);

            const response = await fetch('/api/onsit/extract-vendors', {
                method: 'POST',
                body: formData,
            });

            const result = await response.json();

            if (result.success && result.vendors) {
                setExtractedVendors(result.vendors);
                toast.success(`Extracted ${result.vendors.length} vendors from video`);
            } else {
                throw new Error(result.error || 'Failed to extract vendors');
            }
        } catch (error) {
            console.error('Video processing failed:', error);
            toast.error('Failed to process video');
        } finally {
            setProcessing(false);
        }
    };

    // Process pasted text
    const handleProcessText = async () => {
        if (!textInput.trim()) {
            toast.error('Please paste some text first');
            return;
        }

        setProcessing(true);

        try {
            const response = await fetch('/api/onsit/extract-vendors', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: 'text',
                    data: textInput,
                }),
            });

            const result = await response.json();

            if (result.success && result.vendors) {
                setExtractedVendors(result.vendors);
                toast.success(`Extracted ${result.vendors.length} vendors`);
            } else {
                throw new Error(result.error || 'Failed to extract vendors');
            }
        } catch (error) {
            console.error('Text processing failed:', error);
            toast.error('Failed to process text');
        } finally {
            setProcessing(false);
        }
    };

    // Add vendors to discovery queue
    const handleAddToQueue = () => {
        if (extractedVendors.length === 0) {
            toast.error('No vendors to add');
            return;
        }

        onVendorsExtracted?.(extractedVendors);
        toast.success(`Added ${extractedVendors.length} vendors to discovery queue`);

        // Reset
        setExtractedVendors([]);
        setImageFile(null);
        setVideoFile(null);
        setTextInput('');
        setPreviewUrl('');
        setOpen(false);
    };

    // Remove vendor from extracted list
    const handleRemoveVendor = (vendor: string) => {
        setExtractedVendors(prev => prev.filter(v => v !== vendor));
    };

    // Clear everything
    const handleClear = () => {
        setExtractedVendors([]);
        setImageFile(null);
        setVideoFile(null);
        setTextInput('');
        setPreviewUrl('');
        if (previewUrl) URL.revokeObjectURL(previewUrl);
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button variant="outline" className="gap-2">
                    <ListPlus className="h-4 w-4" />
                    Add Vendor List
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[600px] max-h-[85vh] overflow-hidden flex flex-col">
                <DialogHeader>
                    <DialogTitle>Extract Vendor List</DialogTitle>
                    <DialogDescription>
                        Upload a screenshot/recording of a cookie consent dialog, or paste the vendor list text.
                    </DialogDescription>
                </DialogHeader>

                <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1">
                    <TabsList className="grid w-full grid-cols-3">
                        <TabsTrigger value="screenshot" className="gap-1.5">
                            <Image className="h-3.5 w-3.5" />
                            Screenshot
                        </TabsTrigger>
                        <TabsTrigger value="recording" className="gap-1.5">
                            <Video className="h-3.5 w-3.5" />
                            Recording
                        </TabsTrigger>
                        <TabsTrigger value="text" className="gap-1.5">
                            <FileText className="h-3.5 w-3.5" />
                            Text
                        </TabsTrigger>
                    </TabsList>

                    {/* Screenshot Tab */}
                    <TabsContent value="screenshot" className="space-y-4">
                        <div className="space-y-2">
                            <Label>Upload Screenshot</Label>
                            <div className={cn(
                                'border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors',
                                imageFile ? 'border-green-500 bg-green-50 dark:bg-green-900/10' : 'border-muted-foreground/25 hover:border-primary/50'
                            )}>
                                <input
                                    type="file"
                                    accept="image/*"
                                    onChange={(e) => handleFileSelect(e, 'image')}
                                    className="hidden"
                                    id="screenshot-upload"
                                />
                                <label htmlFor="screenshot-upload" className="cursor-pointer">
                                    {imageFile ? (
                                        <>
                                            <CheckCircle2 className="h-10 w-10 mx-auto mb-2 text-green-500" />
                                            <p className="text-sm font-medium">{imageFile.name}</p>
                                        </>
                                    ) : (
                                        <>
                                            <Upload className="h-10 w-10 mx-auto mb-2 text-muted-foreground" />
                                            <p className="text-sm font-medium">Click to upload screenshot</p>
                                            <p className="text-xs text-muted-foreground mt-1">PNG, JPG, WEBP</p>
                                        </>
                                    )}
                                </label>
                            </div>
                        </div>

                        {previewUrl && activeTab === 'screenshot' && (
                            <div className="border rounded-lg overflow-hidden">
                                <img src={previewUrl} alt="Preview" className="w-full h-auto max-h-48 object-contain" />
                            </div>
                        )}

                        <Button
                            onClick={handleProcessScreenshot}
                            disabled={!imageFile || processing}
                            className="w-full"
                        >
                            {processing ? (
                                <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Processing...</>
                            ) : (
                                <><Sparkles className="h-4 w-4 mr-2" /> Extract Vendors with AI</>
                            )}
                        </Button>
                    </TabsContent>

                    {/* Recording Tab */}
                    <TabsContent value="recording" className="space-y-4">
                        <div className="space-y-2">
                            <Label>Upload Screen Recording</Label>
                            <div className={cn(
                                'border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors',
                                videoFile ? 'border-green-500 bg-green-50 dark:bg-green-900/10' : 'border-muted-foreground/25 hover:border-primary/50'
                            )}>
                                <input
                                    type="file"
                                    accept="video/*"
                                    onChange={(e) => handleFileSelect(e, 'video')}
                                    className="hidden"
                                    id="video-upload"
                                />
                                <label htmlFor="video-upload" className="cursor-pointer">
                                    {videoFile ? (
                                        <>
                                            <CheckCircle2 className="h-10 w-10 mx-auto mb-2 text-green-500" />
                                            <p className="text-sm font-medium">{videoFile.name}</p>
                                        </>
                                    ) : (
                                        <>
                                            <Upload className="h-10 w-10 mx-auto mb-2 text-muted-foreground" />
                                            <p className="text-sm font-medium">Click to upload recording</p>
                                            <p className="text-xs text-muted-foreground mt-1">MP4, WEBM, MOV</p>
                                        </>
                                    )}
                                </label>
                            </div>
                        </div>

                        <Button
                            onClick={handleProcessVideo}
                            disabled={!videoFile || processing}
                            className="w-full"
                        >
                            {processing ? (
                                <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Processing...</>
                            ) : (
                                <><Sparkles className="h-4 w-4 mr-2" /> Extract Vendors from Video</>
                            )}
                        </Button>
                    </TabsContent>

                    {/* Text Tab */}
                    <TabsContent value="text" className="space-y-4">
                        <div className="space-y-2">
                            <Label>Paste Vendor List</Label>
                            <Textarea
                                value={textInput}
                                onChange={(e) => setTextInput(e.target.value)}
                                placeholder="Paste the vendor list from the cookie consent dialog here..."
                                rows={8}
                                className="font-mono text-xs"
                            />
                        </div>

                        <Button
                            onClick={handleProcessText}
                            disabled={!textInput.trim() || processing}
                            className="w-full"
                        >
                            {processing ? (
                                <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Processing...</>
                            ) : (
                                <><Sparkles className="h-4 w-4 mr-2" /> Extract Vendors</>
                            )}
                        </Button>
                    </TabsContent>
                </Tabs>

                {/* Extracted Vendors List */}
                {extractedVendors.length > 0 && (
                    <div className="space-y-2 border-t pt-4">
                        <div className="flex items-center justify-between">
                            <Label>Extracted Vendors ({extractedVendors.length})</Label>
                            <Button variant="ghost" size="sm" onClick={handleClear}>
                                <X className="h-3 w-3 mr-1" />
                                Clear
                            </Button>
                        </div>
                        <ScrollArea className="h-32 border rounded-lg p-2">
                            <div className="flex flex-wrap gap-1.5">
                                {extractedVendors.map((vendor, i) => (
                                    <Badge key={i} variant="secondary" className="gap-1">
                                        {vendor}
                                        <button
                                            onClick={() => handleRemoveVendor(vendor)}
                                            className="hover:text-destructive"
                                        >
                                            <X className="h-3 w-3" />
                                        </button>
                                    </Badge>
                                ))}
                            </div>
                        </ScrollArea>
                    </div>
                )}

                <DialogFooter>
                    <Button variant="outline" onClick={() => setOpen(false)}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleAddToQueue}
                        disabled={extractedVendors.length === 0}
                    >
                        <ListPlus className="h-4 w-4 mr-2" />
                        Add {extractedVendors.length} to Discovery
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
