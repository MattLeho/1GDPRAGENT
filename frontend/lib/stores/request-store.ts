
import { create } from 'zustand';

// --- Types ---

export interface AnalysisResult {
    dpo_email: string;
    address: string;
    data_collected: string[];
}

export interface Profile {
    id: string;
    identity_name: string;
    contactName?: string;
    contactEmail?: string;
    // Encrypted fields are stored as is
    encrypted_name: string;
    encrypted_email: string;
    encrypted_address: string;
    requestDetails?: {
        fieldKey: string;
        encryptedValue: string;
    }[];
}

export type RequestScope = 'all' | 'specific' | 'deletion';

export interface DateRange {
    from: Date | undefined;
    to: Date | undefined;
}

export interface RequestState {
    // Wizard State
    currentStep: number;

    // Form Data
    targetUrl: string;
    analysisResult: AnalysisResult | null;
    selectedIdentity: Profile | null;

    // Step 3: Scope
    isDeletionRequest: boolean;
    dateRange: DateRange;
    additionalNotes: string;

    isEncrypted: boolean;

    // Actions
    setStep: (step: number) => void;
    nextStep: () => void;
    prevStep: () => void;

    setTargetUrl: (url: string) => void;
    setAnalysisResult: (result: AnalysisResult | null) => void;
    setIdentity: (identity: Profile | null) => void;

    setDeletionRequest: (isDeletion: boolean) => void;
    setDateRange: (range: DateRange) => void;
    setNotes: (notes: string) => void;

    toggleEncryption: (enabled: boolean) => void;

    reset: () => void;

    // Graph Integration
    graphData: { id: string, label: string, emails: string[] }[];
    fetchGraphData: () => Promise<void>;
}

// --- Store ---

export const useRequestStore = create<RequestState>((set) => ({
    // Initial State
    currentStep: 1,
    targetUrl: '',
    analysisResult: null,
    selectedIdentity: null,

    isDeletionRequest: false,
    dateRange: { from: undefined, to: undefined },
    additionalNotes: '',

    isEncrypted: true,
    graphData: [],

    // Actions
    setStep: (step) => set({ currentStep: step }),
    nextStep: () => set((state) => ({ currentStep: state.currentStep + 1 })),
    prevStep: () => set((state) => ({ currentStep: Math.max(1, state.currentStep - 1) })),

    setTargetUrl: (url) => set({ targetUrl: url }),
    setAnalysisResult: (result) => set({ analysisResult: result }),
    setIdentity: (identity) => set({ selectedIdentity: identity }),

    setDeletionRequest: (isDeletion) => set({ isDeletionRequest: isDeletion }),
    setDateRange: (range) => set({ dateRange: range }),
    setNotes: (notes) => set({ additionalNotes: notes }),

    toggleEncryption: (enabled) => set({ isEncrypted: enabled }),

    fetchGraphData: async () => {
        try {
            const res = await fetch('/api/identities');
            if (res.ok) {
                const data = await res.json();
                set({ graphData: data });
            }
        } catch (e) {
            console.error("Failed to load graph data", e);
        }
    },

    reset: () => set({
        currentStep: 1,
        targetUrl: '',
        analysisResult: null,
        selectedIdentity: null,
        isDeletionRequest: false,
        dateRange: { from: undefined, to: undefined },
        additionalNotes: '',
        isEncrypted: true,
        graphData: [],
    }),
}));
