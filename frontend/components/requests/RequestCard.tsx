"use client";

import { Request } from "@/lib/actions/requests";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Maximize2, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface RequestCardProps {
    request: Request;
    onViewDetails: (request: Request) => void;
    onDelete?: (requestId: string) => void;
}

export function RequestCard({ request, onViewDetails, onDelete }: RequestCardProps) {
    // Helper to determine status color
    const getStatusColor = (status: string) => {
        switch (status) {
            case 'processing': return 'bg-blue-500 hover:bg-blue-600 border-blue-200 text-blue-700 bg-blue-50';
            case 'action_required': return 'bg-red-500 hover:bg-red-600 border-red-200 text-red-700 bg-red-50';
            case 'completed': return 'bg-green-500 hover:bg-green-600 border-green-200 text-green-700 bg-green-50';
            case 'scheduled': return 'bg-orange-500 hover:bg-orange-600 border-orange-200 text-orange-700 bg-orange-50';
            default: return 'bg-gray-500 hover:bg-gray-600 border-gray-200 text-gray-700 bg-gray-50';
        }
    };

    const statusStyles = {
        processing: 'bg-blue-100 text-blue-700 border-blue-200',
        action_required: 'bg-red-100 text-red-700 border-red-200',
        completed: 'bg-green-100 text-green-700 border-green-200',
        scheduled: 'bg-orange-100 text-orange-700 border-orange-200',
        draft: 'bg-gray-100 text-gray-700 border-gray-200',
    };

    const statusLabel = request.status.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

    const handleDelete = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (onDelete && confirm(`Delete request for "${request.company_name}"? This will permanently remove all associated files, chat messages, and data.`)) {
            onDelete(request.id);
        }
    };

    return (
        <Card className="p-4 flex gap-4 hover:shadow-md transition-shadow duration-200 bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800">
            {/* Left Column: Logo Container */}
            <div className="w-24 h-24 shrink-0 rounded-lg border bg-zinc-50 dark:bg-zinc-950 flex items-center justify-center p-2">
                <Avatar className="h-full w-full rounded-none">
                    <AvatarImage
                        src={`https://logo.clearbit.com/${request.domain || request.company_name}.com`}
                        alt={request.company_name}
                        className="object-contain"
                    />
                    <AvatarFallback className="text-2xl font-bold text-zinc-300">
                        {request.company_name.substring(0, 1).toUpperCase()}
                    </AvatarFallback>
                </Avatar>
            </div>

            {/* Right Column: Details */}
            <div className="flex-1 flex flex-col justify-between min-w-0">

                {/* Top: Name + Actions */}
                <div className="flex items-start justify-between">
                    <h3 className="font-bold text-lg truncate pr-2" title={request.company_name}>
                        {request.company_name}
                    </h3>
                    <div className="flex items-center gap-1 -mt-1 -mr-2">
                        {onDelete && (
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-zinc-400 hover:text-red-600"
                                onClick={handleDelete}
                                title="Delete request"
                            >
                                <Trash2 className="h-4 w-4" />
                            </Button>
                        )}
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-zinc-400 hover:text-zinc-600"
                            onClick={() => onViewDetails(request)}
                        >
                            <Maximize2 className="h-4 w-4" />
                        </Button>
                    </div>
                </div>

                {/* Middle: Status Badge */}
                <div className="space-y-2">
                    <Badge variant="outline" className={cn("font-medium border shadow-none", statusStyles[request.status])}>
                        {statusLabel}
                    </Badge>

                    {/* Status Progress Indicator */}
                    {request.status === 'completed' ? (
                        <div className="flex items-center gap-2 text-green-600 dark:text-green-400 text-xs">
                            <div className="h-1.5 w-1.5 rounded-full bg-green-500" />
                            <span>Completed</span>
                        </div>
                    ) : (
                        <div className="relative h-1 w-full bg-zinc-100 dark:bg-zinc-800 rounded-full mt-2">
                            <div
                                className={cn(
                                    "absolute left-0 top-0 h-full rounded-full transition-all",
                                    request.status === 'action_required' ? 'bg-red-500' : 'bg-blue-500'
                                )}
                                style={{ width: `${Math.min(request.progress || 10, 100)}%` }}
                            />
                        </div>
                    )}
                </div>

                {/* Bottom: Notes + Date */}
                <div className="mt-2 flex items-center justify-between">
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 truncate flex-1 pr-2">
                        {request.notes || "No notes"}
                    </p>
                    <span className="text-xs text-zinc-400 dark:text-zinc-500 shrink-0">
                        {new Date(request.created_at).toLocaleDateString()}
                    </span>
                </div>

            </div>
        </Card>
    );
}

