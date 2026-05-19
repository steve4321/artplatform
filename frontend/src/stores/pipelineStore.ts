import { create } from 'zustand';
import client from '../api/client';
import type { PipelineRun, PipelineStep, PipelineType, UsageType, OutputSize, OutputFormat } from '../types';

export type { PipelineRun, PipelineStep };

export type PipelineStatus = 'pending' | 'running' | 'completed' | 'failed';

interface Pipeline2DConfig {
  targetSize: OutputSize;
  removeBackground: boolean;
  outputType: OutputFormat;
  usageType: UsageType;
}

interface PipelineState {
  currentRun: PipelineRun | null;
  steps: PipelineStep[];
  isLoading: boolean;
  error: string | null;
  selectedStageIndex: number | null;
  startPipeline: (
    prompt: string,
    negativePrompt?: string,
    stylePreset?: string,
    quality?: string,
    pipelineType?: PipelineType,
    config2d?: Pipeline2DConfig
  ) => Promise<void>;
  fetchPipelineStatus: (pipelineId: string) => Promise<void>;
  resetPipeline: () => void;
  selectStage: (index: number | null) => void;
  getCurrentModelUrl: () => string | null;
  getCurrentImageUrls: () => string[];
  pollStatus: (pipelineId: string) => void;
  deletePipeline: (pipelineId: string) => Promise<void>;
  retryPipeline: (pipelineId: string) => Promise<void>;
}

let pollIntervalId: ReturnType<typeof setInterval> | null = null;
let pollCount = 0;
const MAX_POLL_COUNT = 150;

const stopPolling = () => {
  if (pollIntervalId) {
    clearInterval(pollIntervalId);
    pollIntervalId = null;
  }
  pollCount = 0;
};

export const usePipelineStore = create<PipelineState>((set, get) => ({
  currentRun: null,
  steps: [],
  isLoading: false,
  error: null,
  selectedStageIndex: null,

  startPipeline: async (
    prompt: string,
    _negativePrompt?: string,
    stylePreset?: string,
    quality?: string,
    pipelineType: PipelineType = '3d_art',
    config2d?: Pipeline2DConfig
  ) => {
    set({ isLoading: true, error: null });
    stopPolling();

    try {
      const requestBody: Record<string, unknown> = {
        prompt,
        config: { stages: {} },
        style_preset: stylePreset || 'realistic',
        quality: quality || 'standard',
        pipeline_type: pipelineType,
      };

      if (pipelineType === '2d_art' && config2d) {
        requestBody.config = {
          stages: {},
          target_size: config2d.targetSize,
          remove_background: config2d.removeBackground,
          output_type: config2d.outputType,
          usage_type: config2d.usageType,
        };
      }

      const response = await client.post('/api/v1/pipelines', requestBody);

      const pipeline = response.data as PipelineRun;
      set({ currentRun: pipeline, steps: pipeline.steps || [], isLoading: false });

      const isTerminal = pipeline.status === 'completed' || pipeline.status === 'failed' || pipeline.status === 'partial';
      if (isTerminal) {
        return;
      }

      pollCount = 0;
      get().pollStatus(pipeline.id);

      pollIntervalId = setInterval(() => {
        pollCount++;
        if (pollCount > MAX_POLL_COUNT) {
          stopPolling();
          set({ error: 'Pipeline timed out (no progress for 5 minutes)' });
          return;
        }
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

  getCurrentImageUrls: () => {
    const { currentRun, steps, selectedStageIndex } = get();

    if (!currentRun || currentRun.status !== 'completed') {
      return [];
    }

    // If a stage is selected, get its output URLs
    if (selectedStageIndex !== null && steps[selectedStageIndex]) {
      const step = steps[selectedStageIndex];
      if (step.status === 'completed' && step.outputArtifactIds.length > 0) {
        return step.outputArtifactIds.map(
          (artifactId, idx) =>
            `/api/v1/pipelines/${currentRun.id}/steps/${step.stageOrder}/output?artifact=${artifactId}&index=${idx}`
        );
      }
    }

    // Get all completed steps' output URLs (for candidate images at stage 1)
    const completedSteps = steps.filter((s) => s.status === 'completed');
    const urls: string[] = [];
    completedSteps.forEach((step) => {
      step.outputArtifactIds.forEach((artifactId, idx) => {
        urls.push(
          `/api/v1/pipelines/${currentRun.id}/steps/${step.stageOrder}/output?artifact=${artifactId}&index=${idx}`
        );
      });
    });

    return urls;
  },

  deletePipeline: async (pipelineId: string) => {
    await client.delete(`/api/v1/pipelines/${pipelineId}`);
    const { currentRun } = get();
    if (currentRun?.id === pipelineId) {
      stopPolling();
      set({ currentRun: null, steps: [], error: null, selectedStageIndex: null });
    }
  },

  retryPipeline: async (pipelineId: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await client.post(`/api/v1/pipelines/${pipelineId}/retry/1`);
      const pipeline = response.data as PipelineRun;
      set({ currentRun: pipeline, steps: pipeline.steps || [], isLoading: false });
      pollIntervalId = setInterval(() => {
        get().pollStatus(pipeline.id);
      }, 2000);
    } catch (err) {
      set({ isLoading: false, error: 'Failed to retry pipeline' });
      throw err;
    }
  },
}));