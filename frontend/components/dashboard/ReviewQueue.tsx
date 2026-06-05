"use client";
import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { FileText, Mail, AlertCircle, CheckCircle, Download, Eye } from 'lucide-react';
import { ReviewDetailModal } from './ReviewDetailModal';

// Support both old and new interfaces
interface ReviewItem {
    id: string;
    type: 'email' | 'file' | 'action' | 'message' | 'data';
    title: string;
    description: string;
    date: string;
    data?: unknown;
    companyName?: string;
    requestId?: string;
}

interface ReviewQueueProps {
    items: ReviewItem[];
}

export function ReviewQueue({ items }: ReviewQueueProps) {
    const [selectedItem, setSelectedItem] = useState<ReviewItem | null>(null);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [readItemIds, setReadItemIds] = useState<Set<string>>(new Set());

    useEffect(() => {
        const frameId = window.requestAnimationFrame(() => {
            try {
                const savedIds = JSON.parse(localStorage.getItem('gdpr-review-queue-read') || '[]');
                if (Array.isArray(savedIds)) {
                    setReadItemIds(new Set(savedIds.filter((id): id is string => typeof id === 'string')));
                }
            } catch {
                setReadItemIds(new Set());
            }
        });

        return () => window.cancelAnimationFrame(frameId);
    }, []);

    const persistReadIds = (ids: Set<string>) => {
        setReadItemIds(ids);
        localStorage.setItem('gdpr-review-queue-read', JSON.stringify([...ids]));
    };

    const markRead = (itemId: string) => {
        const nextIds = new Set(readItemIds);
        nextIds.add(itemId);
        persistReadIds(nextIds);
    };

    const markAllRead = () => {
        persistReadIds(new Set([...readItemIds, ...items.map(item => item.id)]));
    };

    const handleReview = (item: ReviewItem) => {
        setSelectedItem(item);
        setIsModalOpen(true);
    };

    const unreadItems = items.filter(item => !readItemIds.has(item.id));

    const getTypeConfig = (type: ReviewItem['type']) => {
        switch (type) {
            case 'email':
            case 'message':
                return {
                    icon: Mail,
                    color: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
                    label: 'Message',
                };
            case 'file':
            case 'data':
                return {
                    icon: Download,
                    color: 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
                    label: 'Data',
                };
            case 'action':
                return {
                    icon: AlertCircle,
                    color: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400',
                    label: 'Action',
                };
            default:
                return {
                    icon: FileText,
                    color: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400',
                    label: 'Item',
                };
        }
    };

    return (
        <>
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium flex items-center justify-between">
                        <span className="flex items-center gap-2">
                            Review Queue
                            {unreadItems.length > 0 && (
                                <Badge variant="destructive" className="text-xs rounded-full px-2">
                                    {unreadItems.length}
                                </Badge>
                            )}
                        </span>
                        {unreadItems.length > 0 && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="text-xs text-muted-foreground"
                                onClick={markAllRead}
                            >
                                Mark All Read
                            </Button>
                        )}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {unreadItems.length === 0 ? (
                        <div className="text-center py-8">
                            <div className="w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto mb-3">
                                <CheckCircle className="h-6 w-6 text-green-600" />
                            </div>
                            <p className="font-medium">All caught up!</p>
                            <p className="text-sm text-muted-foreground">No items to review</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {unreadItems.map((item) => {
                                const config = getTypeConfig(item.type);
                                const Icon = config.icon;

                                return (
                                    <div
                                        key={item.id}
                                        className="flex items-start gap-3 p-3 rounded-lg border bg-zinc-50 dark:bg-zinc-900 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                                    >
                                        <div className={`p-2 rounded-lg shrink-0 ${config.color}`}>
                                            <Icon className="h-4 w-4" />
                                        </div>

                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <h4 className="font-medium text-sm truncate">{item.title}</h4>
                                                <Badge variant="outline" className="text-[10px] shrink-0">
                                                    {config.label}
                                                </Badge>
                                            </div>
                                            <p className="text-xs text-muted-foreground line-clamp-1 mt-0.5">
                                                {item.description}
                                            </p>
                                            <p className="text-[11px] text-muted-foreground mt-1">
                                                {item.date}
                                            </p>
                                        </div>

                                        <div className="flex shrink-0 items-center gap-2">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => handleReview(item)}
                                            >
                                                <Eye className="h-3 w-3 mr-1" />
                                                Review
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => markRead(item.id)}
                                                className="text-xs text-muted-foreground"
                                            >
                                                Mark read
                                            </Button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </CardContent>
            </Card>

            <ReviewDetailModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                item={selectedItem}
            />
        </>
    );
}

