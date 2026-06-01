'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
    Search, Shield, AlertTriangle, CheckCircle2, Clock,
    ExternalLink, Loader2, RefreshCw, Plus, X
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface Broker {
    id: string;
    name: string;
    domain: string;
    category: 'marketing' | 'background' | 'people_search' | 'advertising';
    status: 'unknown' | 'found' | 'not_found' | 'removed' | 'pending';
    lastChecked?: Date;
}

const KNOWN_BROKERS: Broker[] = [
    { id: '1', name: 'Acxiom', domain: 'acxiom.com', category: 'marketing', status: 'unknown' },
    { id: '2', name: 'Spokeo', domain: 'spokeo.com', category: 'people_search', status: 'unknown' },
    { id: '3', name: 'BeenVerified', domain: 'beenverified.com', category: 'background', status: 'unknown' },
    { id: '4', name: 'Whitepages', domain: 'whitepages.com', category: 'people_search', status: 'unknown' },
    { id: '5', name: 'Intelius', domain: 'intelius.com', category: 'people_search', status: 'unknown' },
    { id: '6', name: 'Oracle Data Cloud', domain: 'oracle.com', category: 'advertising', status: 'unknown' },
];

export function DatabrokerScanner() {
    const [brokers, setBrokers] = useState<Broker[]>(KNOWN_BROKERS);
    const [scanning, setScanning] = useState(false);
    const [progress, setProgress] = useState(0);
    const [newBroker, setNewBroker] = useState('');

    const handleScan = async () => {
        setScanning(true);
        setProgress(0);

        for (let i = 0; i < brokers.length; i++) {
            await new Promise(r => setTimeout(r, 500));
            setProgress(((i + 1) / brokers.length) * 100);

            // Simulate random scan results
            const statuses: Broker['status'][] = ['found', 'not_found', 'pending'];
            const randomStatus = statuses[Math.floor(Math.random() * statuses.length)];

            setBrokers(prev => prev.map((b, idx) =>
                idx === i ? { ...b, status: randomStatus, lastChecked: new Date() } : b
            ));
        }

        setScanning(false);
        const found = brokers.filter(b => b.status === 'found').length;
        toast.success('Scan complete', {
            description: `Found data on ${found} brokers`
        });
    };

    const handleAddBroker = () => {
        if (!newBroker.trim()) return;
        const domain = newBroker.includes('.') ? newBroker : `${newBroker}.com`;
        setBrokers(prev => [...prev, {
            id: Date.now().toString(),
            name: newBroker.charAt(0).toUpperCase() + newBroker.slice(1),
            domain,
            category: 'people_search',
            status: 'unknown',
        }]);
        setNewBroker('');
        toast.success('Broker added');
    };

    const handleRemoveBroker = (id: string) => {
        setBrokers(prev => prev.filter(b => b.id !== id));
    };

    const handleRequestRemoval = (broker: Broker) => {
        toast.info(`Removal request queued for ${broker.name}`, {
            description: 'Agent will send opt-out request'
        });
        setBrokers(prev => prev.map(b =>
            b.id === broker.id ? { ...b, status: 'pending' } : b
        ));
    };

    const getStatusBadge = (status: Broker['status']) => {
        const config = {
            found: { icon: <AlertTriangle className="h-3 w-3" />, class: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300' },
            not_found: { icon: <CheckCircle2 className="h-3 w-3" />, class: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' },
            removed: { icon: <CheckCircle2 className="h-3 w-3" />, class: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' },
            pending: { icon: <Clock className="h-3 w-3" />, class: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300' },
            unknown: { icon: <Search className="h-3 w-3" />, class: 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300' },
        };
        const c = config[status];
        return (
            <Badge variant="secondary" className={cn('text-xs gap-1', c.class)}>
                {c.icon}
                {status.replace('_', ' ')}
            </Badge>
        );
    };

    const foundCount = brokers.filter(b => b.status === 'found').length;
    const scannedCount = brokers.filter(b => b.status !== 'unknown').length;

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <Shield className="h-4 w-4 text-indigo-500" />
                        Databroker Scanner
                    </CardTitle>
                    <Badge variant={foundCount > 0 ? 'destructive' : 'secondary'} className="text-xs">
                        {foundCount} found
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Add Broker */}
                <div className="flex gap-2">
                    <Input
                        placeholder="Add broker domain..."
                        value={newBroker}
                        onChange={(e) => setNewBroker(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleAddBroker()}
                        className="h-8 text-sm"
                    />
                    <Button size="sm" variant="outline" onClick={handleAddBroker} className="h-8">
                        <Plus className="h-3 w-3" />
                    </Button>
                </div>

                {/* Progress */}
                {scanning && (
                    <div className="space-y-1">
                        <Progress value={progress} className="h-2" />
                        <p className="text-xs text-muted-foreground text-center">
                            Scanning {Math.round(progress)}%
                        </p>
                    </div>
                )}

                {/* Broker List */}
                <ScrollArea className="h-48">
                    <div className="space-y-2">
                        {brokers.map((broker) => (
                            <div
                                key={broker.id}
                                className="flex items-center gap-2 p-2 rounded-lg border text-sm hover:bg-muted/50"
                            >
                                <div className="flex-1 min-w-0">
                                    <p className="font-medium truncate">{broker.name}</p>
                                    <p className="text-xs text-muted-foreground">{broker.domain}</p>
                                </div>
                                {getStatusBadge(broker.status)}
                                {broker.status === 'found' && (
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-7 text-xs"
                                        onClick={() => handleRequestRemoval(broker)}
                                    >
                                        Remove
                                    </Button>
                                )}
                                <Button
                                    size="icon"
                                    variant="ghost"
                                    className="h-6 w-6"
                                    onClick={() => handleRemoveBroker(broker.id)}
                                >
                                    <X className="h-3 w-3" />
                                </Button>
                            </div>
                        ))}
                    </div>
                </ScrollArea>

                {/* Scan Button */}
                <Button onClick={handleScan} disabled={scanning} className="w-full">
                    {scanning ? (
                        <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Scanning...
                        </>
                    ) : (
                        <>
                            <Search className="mr-2 h-4 w-4" />
                            Scan {brokers.length} Brokers
                        </>
                    )}
                </Button>
            </CardContent>
        </Card>
    );
}
