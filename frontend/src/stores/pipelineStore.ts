import { create } from 'zustand';

export type PipelineStatus = 'pending' | 'running' | 'completed' | 'failed';
export type StepStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface PipelineStep {
  id: string;
  stage: string;
  status: StepStatus;
  startedAt: string | null;
  completedAt: string | null;
  error: string | null;
}

export interface PipelineRun {
  id: string;
  prompt: string;
  status: PipelineStatus;
  steps: PipelineStep[];
  createdAt: string;
  completedAt: string | null;
  error: string | null;
}

interface PipelineState {
  currentRun: PipelineRun | null;
  steps: PipelineStep[];
  isLoading: boolean;
  error: string | null;
  startPipeline: (prompt: string) => Promise<void>;
  fetchCurrentRun: () => Promise<void>;
  resetPipeline: () => void;
}

export const usePipelineStore = create<PipelineState>((set) => ({
  currentRun: null,
  steps: [],
  isLoading: false,
  error: null,
  startPipeline: async (_prompt: string) => {
    set({ isLoading: true, error: null });
    try {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      set({ isLoading: false });
    } catch (err) {
      set({ isLoading: false, error: 'Failed to start pipeline' });
    }
  },
  fetchCurrentRun: async () => {
    set({ isLoading: true });
    try {
      await new Promise((resolve) => setTimeout(resolve, 500));
      set({ isLoading: false });
    } catch {
      set({ isLoading: false, error: 'Failed to fetch pipeline' });
    }
  },
  resetPipeline: () => set({ currentRun: null, steps: [], error: null }),
}));