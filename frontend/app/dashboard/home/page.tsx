import Link from 'next/link';
import { getEnhancedDashboardStats } from '@/lib/actions/dashboard';
import { getRequests } from '@/lib/actions/requests';
import { getUnreadItems } from '@/lib/actions/messages';

// Components
import { StatsOverview } from '@/components/dashboard/StatsOverview';
import { PrivacyScoreCard } from '@/components/dashboard/PrivacyScoreCard';
import { RequestsTimeline } from '@/components/dashboard/RequestsTimeline';
import { TopDataHolders } from '@/components/dashboard/TopDataHolders';
import { QuickActions } from '@/components/dashboard/QuickActions';
import { ComplianceGauge } from '@/components/dashboard/ComplianceGauge';
import { DataVolumeChart } from '@/components/dashboard/DataVolumeChart';
import { TaskWidget } from '@/components/dashboard/TaskWidget';
import { ReviewQueue } from '@/components/dashboard/ReviewQueue';
import { AgentManager } from '@/components/dashboard/AgentManager';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Sparkles, ArrowRight, Shield, Zap } from 'lucide-react';

export const dynamic = 'force-dynamic';

export default async function DashboardHome() {
    // Fetch all data in parallel
    const [stats, pendingRequests, reviewItems] = await Promise.all([
        getEnhancedDashboardStats(),
        getRequests('', 'processing'),
        getUnreadItems(),
    ]);

    // Transform pending requests for TaskWidget
    const taskData = pendingRequests.slice(0, 5).map(r => ({
        id: r.id,
        companyName: r.company_name,
        status: r.status,
        dueDate: 'Action Required'
    }));

    // Get current date for greeting
    const hour = new Date().getHours();
    const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
    const nonZeroVolumeByCompany = stats.volumeByCompany.filter(item => item.value > 0);

    return (
        <div className="space-y-8 pb-8">
            {/* Hero Section */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-500 p-8 text-white">
                {/* Background Pattern */}
                <div className="absolute inset-0 opacity-10">
                    <div className="absolute top-0 left-0 w-40 h-40 bg-white rounded-full blur-3xl" />
                    <div className="absolute bottom-0 right-0 w-60 h-60 bg-white rounded-full blur-3xl" />
                </div>

                <div className="relative flex flex-col md:flex-row md:items-center md:justify-between gap-6">
                    <div>
                        <div className="flex items-center gap-2 mb-2">
                            <Badge variant="secondary" className="bg-white/20 text-white border-none">
                                <Sparkles className="h-3 w-3 mr-1" />
                                GDPR Agent Active
                            </Badge>
                        </div>
                        <h1 className="text-3xl md:text-4xl font-bold">{greeting}!</h1>
                        <p className="text-white/80 mt-2 max-w-md">
                            Your privacy dashboard is ready. You have{' '}
                            <span className="font-semibold text-white">{stats.pendingActions} pending actions</span> and{' '}
                            <span className="font-semibold text-white">{reviewItems.length} items</span> to review.
                        </p>

                        <div className="flex flex-wrap gap-3 mt-6">
                            <Link href="/requests/new">
                                <Button className="bg-white text-indigo-600 hover:bg-white/90 shadow-lg">
                                    <Zap className="h-4 w-4 mr-2" />
                                    New Request
                                </Button>
                            </Link>
                            <Link href="/dashboard/graph">
                                <Button variant="outline" className="border-white/30 text-white hover:bg-white/10">
                                    View Data Graph
                                    <ArrowRight className="h-4 w-4 ml-2" />
                                </Button>
                            </Link>
                        </div>
                    </div>

                    {/* Privacy Score Preview */}
                    <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 min-w-[200px]">
                        <div className="flex items-center gap-3">
                            <div className="p-3 rounded-full bg-white/20">
                                <Shield className="h-6 w-6" />
                            </div>
                            <div>
                                <p className="text-sm text-white/70">Privacy Score</p>
                                <p className="text-4xl font-bold">{stats.privacyScore}</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Stats Overview */}
            <StatsOverview
                totalRequests={stats.totalRequests}
                pendingActions={stats.pendingActions}
                completedRequests={stats.completedRequests}
                dataRetrievedGB={stats.dataRetrievedGB}
                avgResponseDays={stats.avgResponseDays}
                gdprDeadlinesMet={stats.gdprDeadlinesMet}
            />

            {/* Main Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left Column - Wider */}
                <div className="lg:col-span-8 space-y-6">
                    {/* Timeline Chart */}
                    <RequestsTimeline data={stats.requestsTimeline} />

                    {/* Two Column Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Data Volume */}
                        <Card>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium">Data Retrieved by Company</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <DataVolumeChart data={stats.volumeByCompany} />
                                {nonZeroVolumeByCompany.length > 0 && (
                                    <div className="grid grid-cols-2 gap-2 mt-4">
                                        {nonZeroVolumeByCompany.slice(0, 4).map((item) => (
                                            <div key={item.name} className="flex items-center gap-2 text-sm">
                                                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                                                <span className="text-muted-foreground truncate">{item.name}</span>
                                                <span className="font-medium ml-auto">{item.value.toFixed(1)}GB</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Compliance Gauge */}
                        <ComplianceGauge
                            deadlinesMet={stats.gdprDeadlinesMet}
                            deadlinesMissed={stats.gdprDeadlinesMissed}
                            avgResponseDays={stats.avgResponseDays}
                            fastestResponseDays={stats.fastestResponseDays}
                        />
                    </div>

                    {/* Review Queue */}
                    <ReviewQueue items={reviewItems} />
                </div>

                {/* Right Column - Sidebar */}
                <div className="lg:col-span-4 space-y-6">
                    {/* Privacy Score Card */}
                    <PrivacyScoreCard
                        score={stats.privacyScore}
                        breakdown={stats.privacyScoreBreakdown}
                    />

                    {/* Quick Actions */}
                    <QuickActions />

                    {/* Top Data Holders */}
                    <TopDataHolders data={stats.topDataHolders} />
                </div>
            </div>

            {/* Bottom Section: Tasks & Agents */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <TaskWidget tasks={taskData} />

                {/* Agent Manager */}
                <AgentManager />

                {/* Graph Preview Card */}
                <Card className="relative overflow-hidden">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium flex items-center justify-between">
                            Your Data Graph
                            <Badge variant="outline" className="text-xs font-normal">
                                {stats.graphNodes} nodes • {stats.graphConnections} connections
                            </Badge>
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="h-[200px] flex items-center justify-center bg-gradient-to-br from-zinc-50 to-zinc-100 dark:from-zinc-900 dark:to-zinc-800 rounded-lg relative overflow-hidden">
                            <svg className="absolute inset-0 w-full h-full opacity-30" viewBox="0 0 400 200">
                                <circle cx="200" cy="100" r="20" fill="#6366f1" />
                                <circle cx="120" cy="60" r="12" fill="#8b5cf6" />
                                <circle cx="280" cy="60" r="12" fill="#8b5cf6" />
                                <circle cx="80" cy="120" r="10" fill="#22c55e" />
                                <circle cx="320" cy="120" r="10" fill="#22c55e" />
                                <line x1="200" y1="100" x2="120" y2="60" stroke="#6366f1" strokeWidth="2" opacity="0.5" />
                                <line x1="200" y1="100" x2="280" y2="60" stroke="#6366f1" strokeWidth="2" opacity="0.5" />
                            </svg>
                            <div className="relative z-10 text-center">
                                <p className="text-sm text-muted-foreground mb-3">
                                    Visualize your digital footprint
                                </p>
                                <Link href="/dashboard/graph">
                                    <Button size="sm">
                                        Explore Graph
                                        <ArrowRight className="h-4 w-4 ml-2" />
                                    </Button>
                                </Link>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
