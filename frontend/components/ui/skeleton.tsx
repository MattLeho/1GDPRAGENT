"use client";

import { cn } from "@/lib/utils";

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
    variant?: "default" | "circular" | "text" | "card";
    animate?: boolean;
}

export function Skeleton({
    className,
    variant = "default",
    animate = true,
    ...props
}: SkeletonProps) {
    const variants = {
        default: "rounded-md",
        circular: "rounded-full",
        text: "rounded h-4 w-full",
        card: "rounded-lg h-32 w-full",
    };

    return (
        <div
            className={cn(
                "bg-muted",
                animate && "animate-pulse",
                variants[variant],
                className
            )}
            {...props}
        />
    );
}

// Pre-built skeleton layouts for common components

export function SkeletonCard() {
    return (
        <div className="rounded-lg border bg-card p-4 space-y-4">
            <div className="flex items-center gap-3">
                <Skeleton variant="circular" className="h-10 w-10" />
                <div className="space-y-2 flex-1">
                    <Skeleton className="h-4 w-1/2" />
                    <Skeleton className="h-3 w-1/3" />
                </div>
            </div>
            <Skeleton className="h-20" />
            <div className="flex gap-2">
                <Skeleton className="h-8 w-20" />
                <Skeleton className="h-8 w-20" />
            </div>
        </div>
    );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
    return (
        <div className="space-y-3">
            {/* Header */}
            <div className="flex gap-4 pb-2 border-b">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 flex-1" />
            </div>
            {/* Rows */}
            {Array.from({ length: rows }).map((_, i) => (
                <div key={i} className="flex gap-4 py-2">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-4 w-20" />
                    <Skeleton className="h-4 flex-1" />
                </div>
            ))}
        </div>
    );
}

export function SkeletonGraph() {
    return (
        <div className="relative h-[500px] w-full rounded-lg border bg-card overflow-hidden">
            {/* Node skeletons */}
            <div className="absolute top-1/4 left-1/4">
                <Skeleton variant="circular" className="h-16 w-16" />
            </div>
            <div className="absolute top-1/3 right-1/3">
                <Skeleton variant="circular" className="h-12 w-12" />
            </div>
            <div className="absolute bottom-1/4 left-1/3">
                <Skeleton variant="circular" className="h-14 w-14" />
            </div>
            <div className="absolute top-1/2 right-1/4">
                <Skeleton variant="circular" className="h-10 w-10" />
            </div>
            <div className="absolute bottom-1/3 right-1/4">
                <Skeleton variant="circular" className="h-12 w-12" />
            </div>
            {/* Loading message */}
            <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-muted-foreground text-sm animate-pulse">
                    Loading graph...
                </div>
            </div>
        </div>
    );
}

export function SkeletonList({ items = 5 }: { items?: number }) {
    return (
        <div className="space-y-3">
            {Array.from({ length: items }).map((_, i) => (
                <div key={i} className="flex items-center gap-3 p-3 rounded-lg border">
                    <Skeleton variant="circular" className="h-8 w-8" />
                    <div className="flex-1 space-y-2">
                        <Skeleton className="h-4 w-3/4" />
                        <Skeleton className="h-3 w-1/2" />
                    </div>
                    <Skeleton className="h-6 w-16 rounded-full" />
                </div>
            ))}
        </div>
    );
}

export function SkeletonForm() {
    return (
        <div className="space-y-6">
            {/* Input fields */}
            {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="space-y-2">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-10 w-full" />
                </div>
            ))}
            {/* Buttons */}
            <div className="flex gap-3 pt-4">
                <Skeleton className="h-10 w-24" />
                <Skeleton className="h-10 w-32" />
            </div>
        </div>
    );
}
