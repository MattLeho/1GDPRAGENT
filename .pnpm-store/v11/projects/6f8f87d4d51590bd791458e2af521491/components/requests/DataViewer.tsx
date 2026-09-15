import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Download, FileJson } from "lucide-react";

interface DataViewerProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    data: unknown; // Format: { "key": "value" } or string
}

export function DataViewer({ isOpen, onClose, title, data }: DataViewerProps) {
    const jsonString = JSON.stringify(data, null, 2);

    const handleDownload = () => {
        const blob = new Blob([jsonString], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${title.replace(/\s+/g, "_")}_data.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-3xl h-[80vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <FileJson className="h-5 w-5 text-primary" />
                        {title}
                    </DialogTitle>
                    <DialogDescription>
                        Review the data returned by the company.
                    </DialogDescription>
                </DialogHeader>

                <div className="flex-1 min-h-0 border rounded-md bg-zinc-950 text-zinc-50 font-mono text-sm relative">
                    <div className="absolute top-2 right-2 z-10">
                        <Button variant="secondary" size="sm" onClick={handleDownload} className="h-8 gap-2">
                            <Download className="h-4 w-4" />
                            Download
                        </Button>
                    </div>
                    <ScrollArea className="h-full w-full p-4">
                        <pre className="whitespace-pre-wrap break-all">
                            {jsonString}
                        </pre>
                    </ScrollArea>
                </div>
            </DialogContent>
        </Dialog>
    );
}
