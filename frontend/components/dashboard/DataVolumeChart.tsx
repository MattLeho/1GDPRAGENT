'use client';

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

interface DataVolumeChartProps {
    data: {
        name: string;
        value: number;
        color: string;
    }[];
}

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-black/90 text-white p-2 rounded text-xs shadow-lg border border-slate-700">
                <p className="font-bold mb-1">{payload[0].name}</p>
                <p>{`${payload[0].value.toFixed(2)} GB`}</p>
            </div>
        );
    }
    return null;
};

export function DataVolumeChart({ data }: DataVolumeChartProps) {
    const totalGB = data.reduce((acc, curr) => acc + curr.value, 0);

    return (
        <div className="h-[300px] w-full relative">
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="text-center">
                    <p className="text-sm text-gray-500 font-medium">Total</p>
                    <p className="text-3xl font-bold text-gray-900">{totalGB.toFixed(1)}<span className="text-sm text-gray-500 font-normal ml-1">GB</span></p>
                </div>
            </div>
            <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                    <Pie
                        data={data}
                        cx="50%"
                        cy="50%"
                        innerRadius={80}
                        outerRadius={110}
                        paddingAngle={2}
                        dataKey="value"
                        onClick={(data) => console.log(`Filter by ${data.name}`)}
                        className="cursor-pointer outline-none"
                    >
                        {data.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} strokeWidth={0} />
                        ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                </PieChart>
            </ResponsiveContainer>
        </div>
    );
}
