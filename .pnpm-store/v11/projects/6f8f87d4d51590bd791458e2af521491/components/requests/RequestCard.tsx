"use client";

import Link from "next/link";
import { Request } from "@/lib/actions/requests";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ArrowUpRight, Ban, Maximize2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface RequestCardProps {
    request: Request;
    onViewDetails: (request: Request) => void;
    onDelete?: (requestId: string) => void;
}

export function RequestCard({ request, onViewDetails, onDelete }: RequestCardProps) {
    const statusStyles: Record<string,string> = {
        processing: 'bg-blue-100 text-blue-700 border-blue-200',
        action_required: 'bg-red-100 text-red-700 border-red-200',
        completed: 'bg-green-100 text-green-700 border-green-200',
        scheduled: 'bg-orange-100 text-orange-700 border-orange-200',
        draft: 'bg-gray-100 text-gray-700 border-gray-200',
    };

    const statusLabel = request.status.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

    const handleDelete = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (onDelete && confirm(`Cancel the request for "${request.company_name}"? Its history, files, messages, and evidence will be retained.`)) {
            onDelete(request.id);
        }
    };

    return (
        <Card className="flex gap-3 bg-white p-3 transition-shadow duration-200 hover:shadow-md dark:bg-zinc-900 sm:gap-4 sm:p-4 border-zinc-200 dark:border-zinc-800">
            {/* Left Column: Logo Container */}
            <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-lg border bg-zinc-50 p-2 dark:bg-zinc-950 sm:h-24 sm:w-24">
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
                    <div className="min-w-0 pr-2">
                        <h3 className="truncate text-base font-bold sm:text-lg" title={request.company_name}>
                            <Link
                                href={`/dashboard/requests/${request.id}`}
                                className="rounded-sm hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            >
                                {request.company_name}
                            </Link>
                        </h3>
                        <Link
                            href={`/dashboard/requests/${request.id}`}
                            className="mt-1 inline-flex min-h-6 items-center gap-1 text-xs font-medium text-primary hover:underline"
                        >
                            Open request <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
                        </Link>
                    </div>
                    <div className="flex items-center gap-1 -mt-1 -mr-2">
                        {onDelete && (
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-10 w-10 text-zinc-400 hover:text-red-600"
                                onClick={handleDelete}
                                title="Cancel request"
                                aria-label={`Cancel ${request.company_name}`}
                            >
                                <Ban className="h-4 w-4" />
                            </Button>
                        )}
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-10 w-10 text-zinc-400 hover:text-zinc-600"
                            onClick={() => onViewDetails(request)}
                            aria-label={`Quick view ${request.company_name}`}
                            title="Quick view"
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

