'use client';

import { useState, useEffect } from 'react';
import { Bell, Check, X, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from '@/components/ui/popover';
import { cn } from '@/lib/utils';

interface Notification {
    id: string;
    type: 'request_created' | 'response_received' | 'data_retrieved' | 'request_completed' | 'agent_run';
    message: string;
    timestamp: Date;
    read: boolean;
    companyName?: string;
}

interface NotificationsBellProps {
    initialNotifications?: Notification[];
}

export function NotificationsBell({ initialNotifications = [] }: NotificationsBellProps) {
    const [notifications, setNotifications] = useState<Notification[]>(initialNotifications);
    const [open, setOpen] = useState(false);

    const unreadCount = notifications.filter((n) => !n.read).length;

    const markAsRead = (id: string) => {
        setNotifications((prev) =>
            prev.map((n) => (n.id === id ? { ...n, read: true } : n))
        );
    };

    const markAllAsRead = () => {
        setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    };

    const dismissNotification = (id: string) => {
        setNotifications((prev) => prev.filter((n) => n.id !== id));
    };

    const formatTime = (date: Date) => {
        const diff = Date.now() - new Date(date).getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 1) return 'Just now';
        if (mins < 60) return `${mins}m ago`;
        const hours = Math.floor(mins / 60);
        if (hours < 24) return `${hours}h ago`;
        return new Date(date).toLocaleDateString();
    };

    const getTypeIcon = (type: string) => {
        switch (type) {
            case 'response_received': return '📩';
            case 'data_retrieved': return '📦';
            case 'request_completed': return '✅';
            case 'agent_run': return '🤖';
            default: return '📝';
        }
    };

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="ghost"
                    size="icon"
                    className="relative text-gray-500 hover:text-gray-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                >
                    <Bell className="h-5 w-5" />
                    {unreadCount > 0 && (
                        <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-red-500 text-[10px] font-bold text-white flex items-center justify-center animate-pulse">
                            {unreadCount > 9 ? '9+' : unreadCount}
                        </span>
                    )}
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-80 p-0" align="end">
                <div className="flex items-center justify-between p-3 border-b">
                    <h4 className="font-semibold text-sm">Notifications</h4>
                    {unreadCount > 0 && (
                        <Button variant="ghost" size="sm" className="text-xs h-6" onClick={markAllAsRead}>
                            Mark all read
                        </Button>
                    )}
                </div>
                <div className="max-h-80 overflow-y-auto">
                    {notifications.length === 0 ? (
                        <div className="p-6 text-center text-sm text-muted-foreground">
                            No notifications
                        </div>
                    ) : (
                        notifications.slice(0, 10).map((notification) => (
                            <div
                                key={notification.id}
                                className={cn(
                                    'flex items-start gap-3 p-3 border-b last:border-0 transition-colors cursor-pointer',
                                    !notification.read ? 'bg-blue-50/50 dark:bg-blue-950/20' : 'hover:bg-muted/50'
                                )}
                                onClick={() => markAsRead(notification.id)}
                            >
                                <span className="text-lg">{getTypeIcon(notification.type)}</span>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium truncate">
                                        {notification.companyName || 'System'}
                                    </p>
                                    <p className="text-xs text-muted-foreground line-clamp-2">
                                        {notification.message}
                                    </p>
                                    <p className="text-[10px] text-muted-foreground mt-1 flex items-center gap-1">
                                        <Clock className="h-2.5 w-2.5" />
                                        {formatTime(notification.timestamp)}
                                    </p>
                                </div>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-6 w-6 opacity-50 hover:opacity-100"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        dismissNotification(notification.id);
                                    }}
                                >
                                    <X className="h-3 w-3" />
                                </Button>
                            </div>
                        ))
                    )}
                </div>
            </PopoverContent>
        </Popover>
    );
}
