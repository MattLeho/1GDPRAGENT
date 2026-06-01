import { getRequests } from "@/lib/actions/requests";
import { RequestsGrid } from "@/components/requests/RequestsGrid";
import { Button } from "@/components/ui/button";
import { AddManualRequestDialog } from "@/components/requests/AddManualRequestDialog";
import Link from "next/link";

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
        <div className="flex flex-col gap-6 p-6 h-full max-w-7xl mx-auto w-full">
            {/* Page Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Access Requests</h1>
                    <p className="text-muted-foreground">Manage and track your data retrieval requests.</p>
                </div>
                <div className="flex items-center gap-3">
                    <AddManualRequestDialog />
                    <Link href="/requests/new">
                        <Button>New Request</Button>
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
