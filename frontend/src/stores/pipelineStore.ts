import { create } from 'zustand';
import client from '../api/client';
import type { PipelineRun, PipelineStep } from '../types';

export type { PipelineRun, PipelineStep };

export type PipelineStatus = 'pending' | 'running' | 'completed' | 'failed';

interface PipelineState {
  currentRun: PipelineRun | null;
  steps: PipelineStep[];
  isLoading: boolean;
  error: string | null;
  selectedStageIndex: number | null;
  startPipeline: (prompt: string, negativePrompt?: string, stylePreset?: string, quality?: string) => Promise<void>;
  fetchPipelineStatus: (pipelineId: string) => Promise<void>;
  resetPipeline: () => void;
  selectStage: (index: number | null) => void;
  getCurrentModelUrl: () => string | null;
  pollStatus: (pipelineId: string) => void;
}

let pollIntervalId: ReturnType<typeof setInterval> | null = null;

const stopPolling = () => {
  if (pollIntervalId) {
    clearInterval(pollIntervalId);
    pollIntervalId = null;
  }
};

export const usePipelineStore = create<PipelineState>((set, get) => ({
  currentRun: null,
  steps: [],
  isLoading: false,
  error: null,
  selectedStageIndex: null,

  startPipeline: async (prompt: string, _negativePrompt?: string, stylePreset?: string, quality?: string) => {
    set({ isLoading: true, error: null });
    stopPolling();

    try {
      const response = await client.post('/api/v1/pipelines', {
        prompt,
        config: { stages: {} },
        style_preset: stylePreset || 'realistic',
        quality: quality || 'standard',
      });

      const pipeline = response.data as PipelineRun;
      set({ currentRun: pipeline, steps: pipeline.steps || [], isLoading: false });

      // Start polling immediately, then every 2 seconds
      get().pollStatus(pipeline.id);

      pollIntervalId = setInterval(() => {
        get().pollStatus(pipeline.id);
      }, 2000);
    } catch (err) {
      set({ isLoading: false, error: 'Failed to start pipeline' });
      throw err;
    }
  },

  fetchPipelineStatus: async (pipelineId: string) => {
    try {
      const response = await client.get(`/api/v1/pipelines/${pipelineId}`);
      const pipeline = response.data as PipelineRun;

      const isCompleted = pipeline.status === 'completed' || pipeline.status === 'failed' || pipeline.status === 'partial';

      set({
        currentRun: pipeline,
        steps: pipeline.steps || [],
      });

      if (isCompleted) {
        stopPolling();
      }
    } catch (err) {
      set({ error: 'Failed to fetch pipeline status' });
      stopPolling();
    }
  },

  pollStatus: (pipelineId: string) => {
    get().fetchPipelineStatus(pipelineId);
  },

  resetPipeline: () => {
    stopPolling();
    set({ currentRun: null, steps: [], error: null, selectedStageIndex: null });
  },

  selectStage: (index: number | null) => {
    set({ selectedStageIndex: index });
  },

  getCurrentModelUrl: () => {
    const { currentRun, steps, selectedStageIndex } = get();

    if (!currentRun || currentRun.status !== 'completed') {
      return null;
    }

    // If a stage is selected, get its output URL
    if (selectedStageIndex !== null && steps[selectedStageIndex]) {
      const step = steps[selectedStageIndex];
      if (step.status === 'completed' && step.outputArtifactIds.length > 0) {
        return `/api/v1/pipelines/${currentRun.id}/steps/${step.stageOrder}/output`;
      }
    }

    // Get the last completed step's output URL
    const completedSteps = steps.filter((s) => s.status === 'completed');
    if (completedSteps.length > 0) {
      const lastStep = completedSteps[completedSteps.length - 1];
      if (lastStep.outputArtifactIds.length > 0) {
        return `/api/v1/pipelines/${currentRun.id}/steps/${lastStep.stageOrder}/output`;
      }
    }

    return null;
  },
}));