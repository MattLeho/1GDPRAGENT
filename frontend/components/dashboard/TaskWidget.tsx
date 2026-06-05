'use client';

import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Play, ListTodo } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Task {
    id: string;
    companyName: string;
    status: 'draft' | 'pending' | 'action_needed' | 'scheduled' | 'processing' | 'action_required' | 'completed';
    dueDate: string;
    logoUrl?: string;
}

interface TaskWidgetProps {
    tasks: Task[];
}

const statusMap: Record<string, { label: string; className: string }> = {
    draft: { label: 'Draft', className: 'bg-slate-100 text-slate-600 hover:bg-slate-100' },
    pending: { label: 'Pending', className: 'bg-yellow-100 text-yellow-700 hover:bg-yellow-100' },
    action_needed: { label: 'Action', className: 'bg-red-100 text-red-700 hover:bg-red-100' },
    // Additional statuses from Request interface
    scheduled: { label: 'Scheduled', className: 'bg-blue-100 text-blue-700 hover:bg-blue-100' },
    processing: { label: 'Processing', className: 'bg-indigo-100 text-indigo-700 hover:bg-indigo-100' },
    action_required: { label: 'Action Required', className: 'bg-orange-100 text-orange-700 hover:bg-orange-100' },
    completed: { label: 'Completed', className: 'bg-green-100 text-green-700 hover:bg-green-100' },
};

export function TaskWidget({ tasks }: TaskWidgetProps) {
    return (
        <Card className="h-full border-gray-200 shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-base font-medium">Ongoing Tasks</CardTitle>
                <ListTodo className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent className="p-0">
                <Table>
                    <TableHeader>
                        <TableRow className="hover:bg-transparent border-gray-100">
                            <TableHead className="w-[50px]"></TableHead>
                            <TableHead>Company</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead className="text-right">Deadline</TableHead>
                            <TableHead className="w-[50px]"></TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {tasks.map((task) => (
                            <TableRow key={task.id} className="hover:bg-slate-50 border-gray-100">
                                <TableCell className="py-3">
                                    <div className="h-8 w-8 rounded bg-gray-100 flex items-center justify-center text-xs font-bold text-gray-500">
                                        {task.companyName.substring(0, 2).toUpperCase()}
                                    </div>
                                </TableCell>
                                <TableCell className="font-medium text-gray-900">{task.companyName}</TableCell>
                                <TableCell>
                                    <Badge variant="outline" className={cn("font-normal border-0", statusMap[task.status]?.className || 'bg-gray-100 text-gray-600')}>
                                        {statusMap[task.status]?.label || task.status}
                                    </Badge>
                                </TableCell>
                                <TableCell className="text-right text-gray-500 text-sm">
                                    {task.dueDate}
                                </TableCell>
                                <TableCell>
                                    <Button size="icon" variant="ghost" className="h-8 w-8 text-blue-600 hover:text-blue-700 hover:bg-blue-50">
                                        <Play className="h-4 w-4" />
                                    </Button>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    );
}
