"use client";

import { motion } from "framer-motion";

interface IdentityMiniMapProps {
    persona: string;
    identityName: string;
    email: string;
    targetCompany: string;
}

export function IdentityMiniMap({ persona, identityName, email, targetCompany }: IdentityMiniMapProps) {
    return (
        <div className="w-full h-32 bg-slate-50 rounded-lg border border-slate-200 overflow-hidden relative flex items-center justify-center">
            <div className="absolute inset-0 pattern-grid opacity-10"></div>

            <div className="flex items-center gap-4 z-10">
                {/* Node: User */}
                <div className="flex flex-col items-center">
                    <div className="w-12 h-12 rounded-full bg-slate-800 text-white flex items-center justify-center font-bold shadow-lg z-10">
                        YOU
                    </div>
                    <span className="text-xs font-semibold mt-2 text-slate-600">Root</span>
                </div>

                {/* Link */}
                <svg width="40" height="20" className="stroke-slate-300">
                    <line x1="0" y1="10" x2="40" y2="10" strokeWidth="2" strokeDasharray="4" />
                </svg>

                {/* Node: Persona */}
                <motion.div
                    key={persona}
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="flex flex-col items-center"
                >
                    <div className="w-10 h-10 rounded-lg bg-indigo-100 border-2 border-indigo-500 text-indigo-700 flex items-center justify-center font-bold shadow-sm z-10">
                        {persona.charAt(0)}
                    </div>
                    <span className="text-xs font-semibold mt-2 text-indigo-600">{persona}</span>
                </motion.div>

                {/* Link */}
                <svg width="40" height="20" className="stroke-slate-300">
                    <line x1="0" y1="10" x2="40" y2="10" strokeWidth="2" />
                </svg>

                {/* Node: Identity */}
                <motion.div
                    key={email}
                    initial={{ y: -10, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    className="flex flex-col items-center"
                >
                    <div className="px-3 py-2 rounded-full bg-white border border-slate-300 text-slate-700 text-xs shadow-sm z-10 whitespace-nowrap max-w-[120px] overflow-hidden text-ellipsis">
                        {email}
                    </div>
                    <span className="text-[10px] mt-1 text-slate-400">Via Email</span>
                </motion.div>

                {/* Link */}
                <svg width="40" height="20" className="stroke-slate-300">
                    <line x1="0" y1="10" x2="40" y2="10" strokeWidth="2" />
                    <polygon points="35,5 40,10 35,15" fill="#cbd5e1" />
                </svg>

                {/* Node: Target */}
                <div className="flex flex-col items-center">
                    <div className="w-12 h-12 rounded-lg bg-emerald-100 border-2 border-emerald-500 text-emerald-700 flex items-center justify-center font-bold shadow-sm z-10">
                        {targetCompany.substring(0, 2).toUpperCase()}
                    </div>
                    <span className="text-xs font-semibold mt-2 text-emerald-600">Target</span>
                </div>
            </div>
        </div>
    );
}
