import { ZipImporter } from '@/components/dashboard/ZipImporter';
import Link from 'next/link';
import { Search, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export const dynamic = 'force-dynamic';

export default function ImportPage() {
    return (
        <div className="mx-auto min-h-0 max-w-5xl space-y-6 overflow-y-auto p-4 sm:p-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Data Import & Scanning</h1>
                <p className="text-muted-foreground">
                    Import GDPR exports as reviewable evidence or start a public-source broker discovery.
                </p>
            </div>

            <div className="flex flex-col gap-6">
                <ZipImporter />
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-lg">
                            <ShieldCheck className="h-5 w-5 text-indigo-500" />
                            Broker discovery
                        </CardTitle>
                        <CardDescription>
                            Search enabled public sources using the authenticated ONSIT workflow. Results depend on the configured providers and must be reviewed before you create a request.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Button asChild className="w-full sm:w-auto">
                            <Link href="/dashboard/onsit">
                                <Search className="mr-2 h-4 w-4" />
                                Open broker discovery
                            </Link>
                        </Button>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
