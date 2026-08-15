import { getRequests } from "@/lib/actions/requests";
import { RequestsGrid } from "@/components/requests/RequestsGrid";
import { Button } from "@/components/ui/button";
import { AddManualRequestDialog } from "@/components/requests/AddManualRequestDialog";
import Link from "next/link";
import { ScanSearch } from "lucide-react";

export const dynamic = 'force-dynamic';

export default async function ViewRequestsPage() {
    // Fetch initial data
    let requests: import("@/lib/actions/requests").Request[] = [];
    try {
        requests = await getRequests();
    } catch (error) {
        console.error("Failed to load requests:", error);
    }

    return (
        <div className="mx-auto flex h-full w-full max-w-7xl min-w-0 flex-col gap-4 sm:gap-6">
            {/* Page Header */}
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                <div>
                    <h1 className="text-xl font-bold tracking-tight sm:text-2xl">Access Requests</h1>
                    <p className="text-sm text-muted-foreground sm:text-base">Manage and track your data retrieval requests.</p>
                </div>
                <div className="grid w-full grid-cols-1 gap-2 sm:grid-cols-3 xl:flex xl:w-auto xl:items-center">
                    <Link href="/dashboard/onsit">
                        <Button variant="outline" className="w-full gap-2 xl:w-auto">
                            <ScanSearch className="h-4 w-4" />
                            Scan for Brokers
                        </Button>
                    </Link>
                    <AddManualRequestDialog />
                    <Link href="/requests/new">
                        <Button className="w-full xl:w-auto">New Request</Button>
                    </Link>
                </div>
            </div>

            {/* Main Content - Grid with integrated SearchToolbar */}
            <div className="flex-1">
                <RequestsGrid initialRequests={requests} />
            </div>
        </div>
    );
}
