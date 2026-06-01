'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect, useCallback } from 'react';
import { useTheme } from 'next-themes';
import {
    LayoutDashboard,
    FileStack,
    PlusCircle,
    Settings,
    Menu,
    ShieldCheck,
    User,
    Share2,
    Sun,
    Moon,
    Search,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { NotificationsBell } from './NotificationsBell';

interface UserProfile {
    username: string;
    email: string;
    profilePictureUrl?: string;
}

interface DashboardLayoutProps {
    children: React.ReactNode;
}

const sidebarItems = [
    {
        name: 'Home',
        href: '/dashboard/home',
        icon: LayoutDashboard,
    },
    {
        name: 'View Requests',
        href: '/dashboard/requests',
        icon: FileStack,
    },
    {
        name: 'Data Graph',
        href: '/dashboard/graph',
        icon: Share2,
    },
    {
        name: 'ONSIT Discovery',
        href: '/dashboard/onsit',
        icon: Search,
    },
    {
        name: 'New Request',
        href: '/requests/new',
        icon: PlusCircle,
        variant: 'cta',
    },
    {
        name: 'Settings',
        href: '/dashboard/settings',
        icon: Settings,
    },
];

export function DashboardLayout({ children }: DashboardLayoutProps) {
    const pathname = usePathname();
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const [mounted, setMounted] = useState(false);
    const { theme, setTheme } = useTheme();
    const [userProfile, setUserProfile] = useState<UserProfile | null>(null);

    // Fetch user profile on mount
    useEffect(() => {
        const loadProfile = async () => {
            try {
                const res = await fetch('/api/settings/profile');
                if (res.ok) {
                    const data = await res.json();
                    if (data.profile) {
                        setUserProfile(data.profile);
                    }
                }
            } catch (error) {
                console.error('Failed to load user profile:', error);
            }
        };
        loadProfile();
    }, []);

    // Prevent hydration mismatch by only rendering theme icon after mount
    useEffect(() => {
        setMounted(true);
    }, []);

    // Helper function to get initials from username
    const getInitials = (name: string): string => {
        return name
            .split(' ')
            .map((word) => word.charAt(0).toUpperCase())
            .slice(0, 2)
            .join('');
    };

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-zinc-950 flex flex-col md:flex-row font-sans text-gray-900 dark:text-zinc-100">
            {/* Mobile Header */}
            <div className="md:hidden flex items-center justify-between p-4 bg-white dark:bg-zinc-900 border-b border-gray-200 dark:border-zinc-800">
                <div className="flex items-center gap-2">
                    <ShieldCheck className="h-6 w-6 text-blue-600" />
                    <span className="font-bold text-lg tracking-tight">GDPR Automator</span>
                </div>
                <Sheet open={isMobileMenuOpen} onOpenChange={setIsMobileMenuOpen}>
                    <SheetTrigger asChild>
                        <Button variant="ghost" size="icon">
                            <Menu className="h-6 w-6" />
                        </Button>
                    </SheetTrigger>
                    <SheetContent side="left" className="w-[280px] p-0">
                        <SidebarContent pathname={pathname} setIsMobileMenuOpen={setIsMobileMenuOpen} />
                    </SheetContent>
                </Sheet>
            </div>

            {/* Desktop Sidebar */}
            <div className="hidden md:flex flex-col w-64 bg-white dark:bg-zinc-900 border-r border-gray-200 dark:border-zinc-800 h-screen sticky top-0">
                <SidebarContent pathname={pathname} />
            </div>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col h-screen overflow-hidden">
                {/* Top Header */}
                <header className="hidden md:flex h-16 bg-white dark:bg-zinc-900 border-b border-gray-200 dark:border-zinc-800 items-center justify-between px-6 sticky top-0 z-10">
                    <h1 className="text-xl font-semibold text-gray-800 dark:text-zinc-100 capitalize">
                        {pathname.split('/').pop()?.replace('-', ' ') || 'Dashboard'}
                    </h1>
                    <div className="flex items-center gap-4">
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                            className="text-gray-500 hover:text-gray-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                        >
                            {mounted ? (theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />) : <Sun className="h-5 w-5 opacity-0" />}
                        </Button>
                        <NotificationsBell />
                        <Separator orientation="vertical" className="h-6" />
                        <div className="flex items-center gap-2">
                            <div className="text-right hidden lg:block">
                                <p className="text-sm font-medium leading-none">{userProfile?.username || 'User Name'}</p>
                                <p className="text-xs text-muted-foreground">{userProfile?.email || 'user@example.com'}</p>
                            </div>
                            <Avatar className="h-8 w-8 cursor-pointer hover:ring-2 hover:ring-blue-100 transition-all">
                                <AvatarImage src={userProfile?.profilePictureUrl || ''} />
                                <AvatarFallback className="bg-blue-100 text-blue-700">
                                    {userProfile?.username ? getInitials(userProfile.username) : <User className="h-4 w-4" />}
                                </AvatarFallback>
                            </Avatar>
                        </div>
                    </div>
                </header>

                {/* Scrollable Page Content */}
                <main className="flex-1 overflow-y-auto p-4 md:p-8 bg-gray-50 dark:bg-zinc-950">
                    {children}
                </main>
            </div>
        </div>
    );
}

// Subcomponent for Sidebar Content (reused for Mobile & Desktop)
function SidebarContent({
    pathname,
    setIsMobileMenuOpen,
}: {
    pathname: string;
    setIsMobileMenuOpen?: (open: boolean) => void;
}) {
    return (
        <div className="flex flex-col h-full bg-white dark:bg-zinc-900 text-gray-900 dark:text-zinc-100">
            {/* Brand */}
            <div className="h-16 flex items-center px-6 border-b border-gray-100 dark:border-zinc-800">
                <ShieldCheck className="h-7 w-7 text-blue-600 mr-2" />
                <span className="font-bold text-xl tracking-tight text-gray-900 dark:text-zinc-100">
                    GDPR<span className="text-blue-600">.</span>Agent
                </span>
            </div>

            {/* Navigation */}
            <nav className="flex-1 py-6 px-4 space-y-2">
                {sidebarItems.map((item) => {
                    const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
                    const isCta = item.variant === 'cta';

                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            onClick={() => setIsMobileMenuOpen?.(false)}
                            className={cn(
                                'flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 group',
                                isActive && !isCta
                                    ? 'bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300'
                                    : 'text-gray-600 dark:text-zinc-400 hover:bg-gray-100 dark:hover:bg-zinc-800 hover:text-gray-900 dark:hover:text-zinc-100',
                                isCta
                                    ? 'bg-blue-600 text-white shadow-md hover:bg-blue-700 hover:shadow-lg mt-4 justify-center text-center'
                                    : ''
                            )}
                        >
                            <item.icon
                                className={cn(
                                    'h-5 w-5',
                                    isActive && !isCta ? 'text-blue-600 dark:text-blue-400' : 'text-gray-500 dark:text-zinc-500 group-hover:text-gray-800 dark:group-hover:text-zinc-200',
                                    isCta ? 'text-white' : ''
                                )}
                            />
                            {item.name}
                        </Link>
                    );
                })}
            </nav>

            {/* Footer / Status Badge */}
            <div className="p-4 border-t border-gray-100 dark:border-zinc-800">
                <div className="bg-slate-50 dark:bg-zinc-800 p-3 rounded-md border border-slate-100 dark:border-zinc-700">
                    <p className="text-xs font-semibold text-slate-500 dark:text-zinc-400 uppercase mb-1">Status</p>
                    <div className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse"></span>
                        <span className="text-xs font-medium text-slate-700 dark:text-zinc-300">System Online</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
