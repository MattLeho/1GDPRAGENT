"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import { Button } from "./button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "./card";

interface ErrorBoundaryProps {
    children: ReactNode;
    fallback?: ReactNode;
    onError?: (error: Error, errorInfo: ErrorInfo) => void;
    resetKeys?: unknown[];
}

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
    errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        this.setState({ errorInfo });
        this.props.onError?.(error, errorInfo);

        // Log to console in development
        if (process.env.NODE_ENV === "development") {
            console.error("ErrorBoundary caught an error:", error, errorInfo);
        }
    }

    componentDidUpdate(prevProps: ErrorBoundaryProps) {
        // Reset error state if resetKeys change
        if (this.state.hasError && this.props.resetKeys) {
            const hasChanged = this.props.resetKeys.some(
                (key, index) => key !== prevProps.resetKeys?.[index]
            );
            if (hasChanged) {
                this.reset();
            }
        }
    }

    reset = () => {
        this.setState({ hasError: false, error: null, errorInfo: null });
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <DefaultErrorFallback
                    error={this.state.error}
                    reset={this.reset}
                />
            );
        }

        return this.props.children;
    }
}

interface ErrorFallbackProps {
    error: Error | null;
    reset?: () => void;
}

export function DefaultErrorFallback({ error, reset }: ErrorFallbackProps) {
    return (
        <div className="flex min-h-[300px] items-center justify-center p-4">
            <Card className="w-full max-w-md">
                <CardHeader className="text-center">
                    <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
                        <AlertTriangle className="h-6 w-6 text-destructive" />
                    </div>
                    <CardTitle>Something went wrong</CardTitle>
                    <CardDescription>
                        An error occurred while rendering this component
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {error && (
                        <div className="rounded-md bg-muted p-3 text-sm">
                            <code className="text-xs text-muted-foreground">
                                {error.message}
                            </code>
                        </div>
                    )}
                </CardContent>
                <CardFooter className="flex gap-2 justify-center">
                    {reset && (
                        <Button onClick={reset} variant="outline" size="sm">
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Try again
                        </Button>
                    )}
                    <Button
                        onClick={() => window.location.href = "/"}
                        variant="ghost"
                        size="sm"
                    >
                        <Home className="mr-2 h-4 w-4" />
                        Go home
                    </Button>
                </CardFooter>
            </Card>
        </div>
    );
}

// Specialized error boundaries for specific contexts

interface GraphErrorBoundaryProps {
    children: ReactNode;
}

export function GraphErrorBoundary({ children }: GraphErrorBoundaryProps) {
    return (
        <ErrorBoundary
            fallback={
                <div className="flex h-[500px] items-center justify-center rounded-lg border bg-card">
                    <div className="text-center space-y-4">
                        <AlertTriangle className="h-12 w-12 text-destructive mx-auto" />
                        <div>
                            <h3 className="font-semibold">Graph Error</h3>
                            <p className="text-sm text-muted-foreground">
                                Failed to render the knowledge graph
                            </p>
                        </div>
                        <Button
                            onClick={() => window.location.reload()}
                            variant="outline"
                            size="sm"
                        >
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Reload page
                        </Button>
                    </div>
                </div>
            }
        >
            {children}
        </ErrorBoundary>
    );
}

export function FormErrorBoundary({ children }: { children: ReactNode }) {
    return (
        <ErrorBoundary
            fallback={
                <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4">
                    <div className="flex items-center gap-2 text-destructive">
                        <AlertTriangle className="h-5 w-5" />
                        <span className="font-medium">Form Error</span>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">
                        Unable to display form. Please refresh the page.
                    </p>
                </div>
            }
        >
            {children}
        </ErrorBoundary>
    );
}
