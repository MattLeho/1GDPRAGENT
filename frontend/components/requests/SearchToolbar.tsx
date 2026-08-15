'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Input } from '@/components/ui/input';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Search, Filter, ArrowUpDown, X } from 'lucide-react';
import { useDebounce } from '@/hooks/use-debounce';

interface SearchToolbarProps {
    onSearchChange: (search: string) => void;
    onFilterChange: (filter: string) => void;
    onSortChange: (sort: string) => void;
}

export function SearchToolbar({ onSearchChange, onFilterChange, onSortChange }: SearchToolbarProps) {
    const searchParams = useSearchParams();
    const router = useRouter();
    const searchInputRef = useRef<HTMLInputElement>(null);

    const [search, setSearch] = useState(searchParams.get('q') || '');
    const [filter, setFilter] = useState(searchParams.get('status') || 'all');
    const [sort, setSort] = useState(searchParams.get('sort') || 'date');

    const debouncedSearch = useDebounce(search, 300);

    useEffect(() => {
        // URL navigation is an external source of truth; mirror Back/Forward changes into the controls.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setSearch(searchParams.get('q') || '');
        setFilter(searchParams.get('status') || 'all');
        setSort(searchParams.get('sort') || 'date');
        if (searchParams.get('focus') === 'search') searchInputRef.current?.focus();
    }, [searchParams]);

    // Update URL and notify parent when debounced search changes
    useEffect(() => {
        onSearchChange(debouncedSearch);

        // Update URL params
        const params = new URLSearchParams(searchParams.toString());
        if (debouncedSearch) {
            params.set('q', debouncedSearch);
        } else {
            params.delete('q');
        }
        router.replace(`?${params.toString()}`, { scroll: false });
    }, [debouncedSearch, onSearchChange, router, searchParams]);

    const handleFilterChange = (value: string) => {
        setFilter(value);
        onFilterChange(value);

        const params = new URLSearchParams(searchParams.toString());
        if (value !== 'all') {
            params.set('status', value);
        } else {
            params.delete('status');
        }
        router.push(`?${params.toString()}`, { scroll: false });
    };

    const handleSortChange = (value: string) => {
        setSort(value);
        onSortChange(value);

        const params = new URLSearchParams(searchParams.toString());
        params.set('sort', value);
        router.push(`?${params.toString()}`, { scroll: false });
    };

    const clearSearch = () => {
        setSearch('');
        onSearchChange('');
    };

    return (
        <div className="grid min-w-0 grid-cols-1 gap-2 rounded-lg border bg-white p-2 shadow-sm dark:bg-zinc-900 sm:grid-cols-2 xl:grid-cols-[minmax(16rem,1fr)_auto_auto] xl:items-center xl:gap-3">
            {/* Search Input */}
            <div className="relative min-w-0 sm:col-span-2 xl:col-span-1">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                    ref={searchInputRef}
                    placeholder="Search companies or brokers..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-9 pr-8 border-none shadow-none focus-visible:ring-0 bg-transparent"
                />
                {search && (
                    <button
                        type="button"
                        aria-label="Clear search"
                        onClick={clearSearch}
                        className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-foreground"
                    >
                        <X className="h-4 w-4" />
                    </button>
                )}
            </div>

            {/* Filter Dropdown */}
            <Select value={filter} onValueChange={handleFilterChange}>
                <SelectTrigger className="w-full min-w-0 border-none shadow-none xl:w-40">
                    <Filter className="h-4 w-4 mr-2 text-muted-foreground" />
                    <SelectValue placeholder="Filter" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="draft">Draft</SelectItem>
                    <SelectItem value="scheduled">Scheduled</SelectItem>
                    <SelectItem value="processing">Processing</SelectItem>
                    <SelectItem value="action_required">Action Required</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                </SelectContent>
            </Select>

            {/* Sort Dropdown */}
            <Select value={sort} onValueChange={handleSortChange}>
                <SelectTrigger className="w-full min-w-0 border-none shadow-none xl:w-44">
                    <ArrowUpDown className="h-4 w-4 mr-2 text-muted-foreground" />
                    <SelectValue placeholder="Sort" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="date">Date (Newest)</SelectItem>
                    <SelectItem value="name">Name (A-Z)</SelectItem>
                    <SelectItem value="status">Status</SelectItem>
                </SelectContent>
            </Select>
        </div>
    );
}
