"use client";

import { useState, useCallback, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Request } from "@/lib/actions/requests";
import { RequestCard } from "./RequestCard";
import { RequestDetailModal } from "./RequestDetailModal";
import { SearchToolbar } from "./SearchToolbar";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

interface RequestsGridProps {
    initialRequests: Request[];
}

function RequestsGridContent({ initialRequests }: RequestsGridProps) {
    const searchParams = useSearchParams();
    const [filteredRequests, setFilteredRequests] = useState<Request[]>(initialRequests);
    const [selectedRequest, setSelectedRequest] = useState<Request | null>(null);
    const [isSheetOpen, setIsSheetOpen] = useState(false);

    const applyFilters = useCallback((search: string, filter: string, sort: string) => {
        let result = [...initialRequests];

        // Apply search
        if (search) {
            const lowerSearch = search.toLowerCase();
            result = result.filter(r =>
                r.company_name.toLowerCase().includes(lowerSearch) ||
                r.domain?.toLowerCase().includes(lowerSearch)
            );
        }

        // Apply status filter
        if (filter && filter !== 'all') {
            result = result.filter(r => r.status === filter);
        }

        // Apply sort
        if (sort === 'name') {
            result.sort((a, b) => a.company_name.localeCompare(b.company_name));
        } else if (sort === 'status') {
            result.sort((a, b) => a.status.localeCompare(b.status));
        } else {
            // Default: date (newest first)
            result.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        }

        setFilteredRequests(result);
    }, [initialRequests]);

    // Initialize filters from URL
    useEffect(() => {
        const q = searchParams.get('q') || '';
        const status = searchParams.get('status') || 'all';
        const sort = searchParams.get('sort') || 'date';

        applyFilters(q, status, sort);
    }, [applyFilters, searchParams]);

    const handleSearchChange = useCallback((search: string) => {
        const filter = searchParams.get('status') || 'all';
        const sort = searchParams.get('sort') || 'date';
        applyFilters(search, filter, sort);
    }, [applyFilters, searchParams]);

    const handleFilterChange = useCallback((filter: string) => {
        const search = searchParams.get('q') || '';
        const sort = searchParams.get('sort') || 'date';
        applyFilters(search, filter, sort);
    }, [applyFilters, searchParams]);

    const handleSortChange = useCallback((sort: string) => {
        const search = searchParams.get('q') || '';
        const filter = searchParams.get('status') || 'all';
        applyFilters(search, filter, sort);
    }, [applyFilters, searchParams]);

    const handleViewDetails = (request: Request) => {
        setSelectedRequest(request);
        setIsSheetOpen(true);
    };

    const handleDeleteRequest = useCallback(async (requestId: string) => {
        try {
            const res = await fetch(`/api/requests/${requestId}`, { method: 'DELETE' });
            const data = await res.json();

            if (data.success) {
                // Remove from local state — triggers re-filter
                setFilteredRequests(prev => prev.filter(r => r.id !== requestId));
                toast.success('Request deleted', {
                    description: 'The request and all associated data have been removed.',
                });
            } else {
                toast.error('Failed to delete', { description: data.error || 'Unknown error' });
            }
        } catch (error) {
            toast.error('Failed to delete request', { description: 'Network error' });
        }
    }, []);

    return (
        <>
            {/* Search Toolbar */}
            <SearchToolbar
                onSearchChange={handleSearchChange}
                onFilterChange={handleFilterChange}
                onSortChange={handleSortChange}
            />

            {/* Results Count */}
            <p className="text-sm text-muted-foreground mt-4 mb-2">
                {filteredRequests.length} {filteredRequests.length === 1 ? 'request' : 'requests'} found
            </p>

            {/* Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredRequests.map((req) => (
                    <RequestCard
                        key={req.id}
                        request={req}
                        onViewDetails={handleViewDetails}
                        onDelete={handleDeleteRequest}
                    />
                ))}
                {filteredRequests.length === 0 && (
                    <div className="col-span-full text-center py-12 text-muted-foreground">
                        No requests match your filters
                    </div>
                )}
            </div>

            <RequestDetailModal
                request={selectedRequest}
                open={isSheetOpen}
                onOpenChange={setIsSheetOpen}
            />
        </>
    );
}

export function RequestsGrid({ initialRequests }: RequestsGridProps) {
    return (
        <Suspense fallback={
            <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        }>
            <RequestsGridContent initialRequests={initialRequests} />
        </Suspense>
    );
}
