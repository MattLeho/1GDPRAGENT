import { ZipImporter } from '@/components/dashboard/ZipImporter';
import { DatabrokerScanner } from '@/components/dashboard/DatabrokerScanner';

export const dynamic = 'force-dynamic';

export default function ImportPage() {
    return (
        <div className="max-w-5xl mx-auto p-6 space-y-6 min-h-0 overflow-y-auto">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Data Import & Scanning</h1>
                <p className="text-muted-foreground">
                    Import your GDPR data exports and scan for data broker exposure.
                </p>
            </div>

            <div className="flex flex-col gap-6">
                <ZipImporter />
                <DatabrokerScanner />
            </div>
        </div>
    );
}
