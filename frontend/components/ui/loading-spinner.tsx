"use client";

import { cn } from "@/lib/utils";

interface LoadingSpinnerProps {
    size?: "sm" | "md" | "lg" | "xl";
    className?: string;
    label?: string;
}

const sizeClasses = {
    sm: "h-4 w-4 border-2",
    md: "h-6 w-6 border-2",
    lg: "h-8 w-8 border-3",
    xl: "h-12 w-12 border-4",
};

export function LoadingSpinner({
    size = "md",
    className,
    label = "Loading..."
}: LoadingSpinnerProps) {
    return (
        <div className={cn("flex items-center gap-2", className)}>
            <div
                className={cn(
                    "animate-spin rounded-full border-primary border-t-transparent",
                    sizeClasses[size]
                )}
                role="status"
                aria-label={label}
            />
            {label && <span className="sr-only">{label}</span>}
        </div>
    );
}

interface FullPageLoaderProps {
    message?: string;
}

export function FullPageLoader({ message = "Loading..." }: FullPageLoaderProps) {
    return (
        <div className="flex min-h-[400px] items-center justify-center">
            <div className="flex flex-col items-center gap-4">
                <LoadingSpinner size="xl" />
                <p className="text-muted-foreground animate-pulse">{message}</p>
            </div>
        </div>
    );
}

interface LoadingOverlayProps {
    isLoading: boolean;
    children: React.ReactNode;
    message?: string;
}

export function LoadingOverlay({
    isLoading,
    children,
    message
}: LoadingOverlayProps) {
    return (
        <div className="relative">
            {children}
            {isLoading && (
                <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
                    <div className="flex flex-col items-center gap-2">
                        <LoadingSpinner size="lg" />
                        {message && (
                            <p className="text-sm text-muted-foreground">{message}</p>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
