import { notFound } from "next/navigation";
import Link from "next/link";
import { getRequestAccountDetails, getRequestById, getRequestHistory, updateRequestStatus } from "@/lib/actions/request-detail";
import { getMessages } from "@/lib/actions/messages";
import { getRequestAnalysis } from "@/lib/actions/policy-analysis";
import { getReceivedData } from "@/lib/actions/data";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import {
    ArrowLeft,
    Clock,
    Mail,
    FileText,
    MapPin,
    Bot,
    User,
    Building2,
    AlertTriangle,
    Database,
    Download,
    CheckCircle2,
    ExternalLink,
} from "lucide-react";

export const dynamic = 'force-dynamic';

interface PageProps {
    params: Promise<{ id: string }>;
}

export default async function RequestDetailPage({ params }: PageProps) {
    const { id } = await params;

    // Fetch all data in parallel
    const [request, messages, analysis, receivedData, history, requestDetails] = await Promise.all([
        getRequestById(id),
        getMessages(id),
        getRequestAnalysis(id),
        getReceivedData(id),
        getRequestById(id).then(r => r?.domain ? getRequestHistory(r.domain, id) : []),
        getRequestAccountDetails(id),
    ]);

    if (!request) {
        notFound();
    }

    const formatDate = (date: Date | string | null) => {
        if (!date) return 'N/A';
        return new Date(date).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    };

    const formatDateTime = (date: Date | string) => {
        return new Date(date).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const getSenderIcon = (sender: string) => {
        switch (sender) {
            case 'agent': return <Bot className="h-4 w-4" />;
            case 'company': return <Building2 className="h-4 w-4" />;
            default: return <User className="h-4 w-4" />;
        }
    };

    const getSenderColor = (sender: string) => {
        switch (sender) {
            case 'agent': return 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300';
            case 'company': return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300';
            default: return 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300';
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'completed': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
            case 'processing': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
            case 'action_required': return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200';
            default: return 'bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200';
        }
    };

    const formatFieldKey = (key: string) => {
        return key
            .replace(/_\d+$/, '')
            .replace(/_/g, ' ')
            .replace(/\b\w/g, (letter) => letter.toUpperCase());
    };

    return (
        <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
            {/* Hero Header */}
            <div className="bg-gradient-to-br from-indigo-600 to-purple-700 dark:from-indigo-800 dark:to-purple-900">
                <div className="max-w-6xl mx-auto px-6 py-8">
                    {/* Back Button */}
                    <Link href="/dashboard/requests" className="inline-flex items-center gap-2 text-white/80 hover:text-white mb-6 transition-colors">
                        <ArrowLeft className="h-4 w-4" />
                        Back to Requests
                    </Link>

                    {/* Company Info */}
                    <div className="flex items-start gap-6">
                        <Avatar className="h-20 w-20 rounded-xl border-4 border-white/20 shadow-lg">
                            <AvatarImage
                                src={`https://logo.clearbit.com/${request.domain || request.company_name}.com`}
                                alt={request.company_name}
                                className="object-contain bg-white"
                            />
                            <AvatarFallback className="rounded-xl text-2xl bg-white/10 text-white">
                                {request.company_name.substring(0, 2).toUpperCase()}
                            </AvatarFallback>
                        </Avatar>

                        <div className="flex-1">
                            <h1 className="text-3xl font-bold text-white mb-2">{request.company_name}</h1>
                            <div className="flex items-center gap-3 flex-wrap">
                                <Badge className={`${getStatusColor(request.status)} uppercase text-xs tracking-wider`}>
                                    {request.status.replace('_', ' ')}
                                </Badge>
                                <Badge variant="outline" className="bg-white/10 text-white border-white/30">
                                    {request.request_type.toUpperCase()} Request
                                </Badge>
                                {request.company_url && (
                                    <a href={request.company_url} target="_blank" className="text-white/80 hover:text-white flex items-center gap-1 text-sm">
                                        <ExternalLink className="h-3 w-3" />
                                        {request.domain}
                                    </a>
                                )}
                            </div>
                        </div>

                        {/* Quick Stats */}
                        <div className="flex gap-6 text-white">
                            <div className="text-center">
                                <div className="text-2xl font-bold">{request.progress || 0}%</div>
                                <div className="text-xs text-white/70">Progress</div>
                            </div>
                            <div className="text-center">
                                <div className="text-2xl font-bold">{messages.length}</div>
                                <div className="text-xs text-white/70">Messages</div>
                            </div>
                        </div>
                    </div>

                    {/* Progress Bar */}
                    <div className="mt-6">
                        <Progress value={request.progress || 0} className="h-2 bg-white/20" />
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="max-w-6xl mx-auto px-6 -mt-4">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Main Column */}
                    <div className="lg:col-span-2">
                        <Card className="shadow-lg">
                            <Tabs defaultValue="activity">
                                <CardHeader className="pb-0">
                                    <TabsList className="grid w-full grid-cols-3">
                                        <TabsTrigger value="activity">Activity</TabsTrigger>
                                        <TabsTrigger value="documents">Documents</TabsTrigger>
                                        <TabsTrigger value="data">Received Data</TabsTrigger>
                                    </TabsList>
                                </CardHeader>

                                {/* Activity Tab */}
                                <TabsContent value="activity" className="m-0">
                                    <CardContent className="pt-6">
                                        {messages.length === 0 ? (
                                            <div className="text-center py-12 text-muted-foreground">
                                                <Clock className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                                <p>No activity yet</p>
                                            </div>
                                        ) : (
                                            <div className="space-y-4">
                                                {messages.map((msg) => (
                                                    <div key={msg.id} className="flex gap-3">
                                                        <div className={`h-8 w-8 rounded-full flex items-center justify-center shrink-0 ${getSenderColor(msg.sender)}`}>
                                                            {getSenderIcon(msg.sender)}
                                                        </div>
                                                        <div className="flex-1 space-y-1">
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-sm font-medium capitalize">{msg.sender}</span>
                                                                <span className="text-xs text-muted-foreground">
                                                                    {formatDateTime(msg.timestamp)}
                                                                </span>
                                                            </div>
                                                            <p className="text-sm text-muted-foreground">{msg.content}</p>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </CardContent>
                                </TabsContent>

                                {/* Documents Tab */}
                                <TabsContent value="documents" className="m-0">
                                    <CardContent className="pt-6">
                                        {analysis ? (
                                            <div className="space-y-6">
                                                {/* Policy Analysis */}
                                                <div className="border rounded-lg p-4 space-y-4">
                                                    <div className="flex items-center justify-between">
                                                        <h4 className="font-medium flex items-center gap-2">
                                                            <FileText className="h-4 w-4 text-indigo-500" />
                                                            Privacy Policy Analysis
                                                        </h4>
                                                        <Badge variant="outline" className="text-xs">
                                                            {formatDateTime(analysis.analyzed_at)}
                                                        </Badge>
                                                    </div>

                                                    {analysis.dpo_email && (
                                                        <div className="flex items-center gap-2 text-sm">
                                                            <Mail className="h-4 w-4 text-muted-foreground" />
                                                            <span className="font-medium">DPO:</span>
                                                            <a href={`mailto:${analysis.dpo_email}`} className="text-blue-600 hover:underline">
                                                                {analysis.dpo_email}
                                                            </a>
                                                        </div>
                                                    )}

                                                    {analysis.company_address && (
                                                        <div className="flex items-start gap-2 text-sm">
                                                            <MapPin className="h-4 w-4 text-muted-foreground mt-0.5" />
                                                            <span>{analysis.company_address}</span>
                                                        </div>
                                                    )}

                                                    <Separator />

                                                    <div>
                                                        <p className="text-xs font-medium text-muted-foreground uppercase mb-2">Data Collected</p>
                                                        <div className="flex flex-wrap gap-1.5">
                                                            {analysis.data_collected.map((item, i) => (
                                                                <Badge key={i} variant="secondary" className="text-xs">
                                                                    {item}
                                                                </Badge>
                                                            ))}
                                                        </div>
                                                    </div>

                                                    {analysis.third_party_sharing.length > 0 && (
                                                        <div>
                                                            <p className="text-xs font-medium text-muted-foreground uppercase mb-2">Third Parties</p>
                                                            <div className="flex flex-wrap gap-1.5">
                                                                {analysis.third_party_sharing.map((item, i) => (
                                                                    <Badge key={i} variant="outline" className="text-xs text-orange-600 border-orange-200">
                                                                        <AlertTriangle className="h-3 w-3 mr-1" />
                                                                        {item}
                                                                    </Badge>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="text-center py-12 text-muted-foreground">
                                                <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                                <p>No policy analysis available</p>
                                            </div>
                                        )}
                                    </CardContent>
                                </TabsContent>

                                {/* Received Data Tab */}
                                <TabsContent value="data" className="m-0">
                                    <CardContent className="pt-6">
                                        {receivedData.length === 0 ? (
                                            <div className="text-center py-12 text-muted-foreground">
                                                <Database className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                                <p>No data received yet</p>
                                            </div>
                                        ) : (
                                            <div className="space-y-3">
                                                {receivedData.map((file) => (
                                                    <div key={file.id} className="flex items-center justify-between p-3 border rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-900">
                                                        <div className="flex items-center gap-3">
                                                            <FileText className="h-5 w-5 text-muted-foreground" />
                                                            <div>
                                                                <p className="font-medium text-sm">{file.file_name}</p>
                                                                <p className="text-xs text-muted-foreground">
                                                                    {file.file_size_mb} MB • {formatDate(file.date_received)}
                                                                </p>
                                                            </div>
                                                        </div>
                                                        <Button variant="ghost" size="sm">
                                                            <Download className="h-4 w-4" />
                                                        </Button>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </CardContent>
                                </TabsContent>
                            </Tabs>
                        </Card>
                    </div>

                    {/* Sidebar */}
                    <div className="space-y-6">
                        {/* Details Card */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-sm">Request Details</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="flex justify-between text-sm">
                                    <span className="text-muted-foreground">Created</span>
                                    <span>{formatDate(request.created_at)}</span>
                                </div>
                                <div className="flex justify-between text-sm">
                                    <span className="text-muted-foreground">Deadline</span>
                                    <span>{formatDate(request.deadline_date)}</span>
                                </div>
                                <div className="flex justify-between text-sm">
                                    <span className="text-muted-foreground">Type</span>
                                    <span className="capitalize">{request.request_type}</span>
                                </div>
                                <Separator />
                                {requestDetails.length > 0 && (
                                    <>
                                        <div>
                                            <span className="text-sm text-muted-foreground">Account Details</span>
                                            <div className="mt-2 flex flex-wrap gap-1.5">
                                                {requestDetails.map((detail) => (
                                                    <Badge key={detail.id} variant="secondary" className="text-xs">
                                                        {formatFieldKey(detail.field_key)}
                                                    </Badge>
                                                ))}
                                            </div>
                                            <p className="mt-2 text-xs text-muted-foreground">
                                                Encrypted values are stored with this request for agent context.
                                            </p>
                                        </div>
                                        <Separator />
                                    </>
                                )}
                                <div>
                                    <span className="text-sm text-muted-foreground">Notes</span>
                                    <p className="text-sm mt-1">{request.notes || 'No notes'}</p>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Actions Card */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-sm">Actions</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2">
                                {request.status !== 'completed' && (
                                    <form
                                        action={async () => {
                                            "use server";
                                            await updateRequestStatus(request.id, 'completed');
                                        }}
                                    >
                                        <Button className="w-full" size="sm" type="submit">
                                            <CheckCircle2 className="mr-2 h-4 w-4" />
                                            Mark Complete
                                        </Button>
                                    </form>
                                )}
                                <Button variant="outline" className="w-full" size="sm" asChild>
                                    <a href={`/api/upload?requestId=${request.id}`} target="_blank" rel="noopener noreferrer">
                                        <Download className="mr-2 h-4 w-4" />
                                        Open Data Export
                                    </a>
                                </Button>
                            </CardContent>
                        </Card>

                        {/* History Card */}
                        {history.length > 0 && (
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-sm">Previous Requests</CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-2">
                                    {history.map((prev) => (
                                        <Link
                                            key={prev.id}
                                            href={`/dashboard/requests/${prev.id}`}
                                            className="flex items-center justify-between p-2 rounded-md border hover:bg-zinc-50 dark:hover:bg-zinc-900"
                                        >
                                            <span className="text-sm">{formatDate(prev.created_at)}</span>
                                            <Badge variant="outline" className="text-xs">
                                                {prev.status}
                                            </Badge>
                                        </Link>
                                    ))}
                                </CardContent>
                            </Card>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
