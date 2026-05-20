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
  resumePipeline: (pipelineId: string, selectedImageIndex: number) => Promise<void>;
  _pollIntervalId: ReturnType<typeof setInterval> | null;
  _pollCount: number;
}

const MAX_POLL_COUNT = 150;

const stopPolling = (set: (partial: Partial<PipelineState>) => void, get: () => PipelineState) => {
  const id = get()._pollIntervalId;
  if (id) clearInterval(id);
  set({ _pollIntervalId: null, _pollCount: 0 });
};

export const usePipelineStore = create<PipelineState>((set, get) => ({
  currentRun: null,
  steps: [],
  isLoading: false,
  error: null,
  selectedStageIndex: null,
  _pollIntervalId: null,
  _pollCount: 0,

  startPipeline: async (
    prompt: string,
    negativePrompt?: string,
    stylePreset?: string,
    quality?: string,
    pipelineType: PipelineType = '3d_scene',
    config2d?: Pipeline2DConfig
  ) => {
    set({ isLoading: true, error: null });
    stopPolling(set, get);

    try {
      const requestBody: Record<string, unknown> = {
        prompt,
        negative_prompt: negativePrompt || '',
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

      set({ _pollCount: 0 });
      get().pollStatus(pipeline.id);

      const id = setInterval(() => {
        const count = get()._pollCount + 1;
        if (count > MAX_POLL_COUNT) {
          stopPolling(set, get);
          set({ error: 'Pipeline timed out (no progress for 5 minutes)' });
          return;
        }
        set({ _pollCount: count });
        get().pollStatus(pipeline.id);
      }, 2000);
      set({ _pollIntervalId: id });
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
        stopPolling(set, get);
      }
    } catch (err) {
      set({ error: 'Failed to fetch pipeline status' });
      stopPolling(set, get);
    }
  },

  pollStatus: (pipelineId: string) => {
    get().fetchPipelineStatus(pipelineId);
  },

  resetPipeline: () => {
    stopPolling(set, get);
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

    const findGlbArtifact = (step: PipelineStep): string | null => {
      const glbKey = step.outputArtifactIds.find((id) => id.endsWith('.glb'));
      return glbKey ? `/local-storage/${glbKey}` : null;
    };

    if (selectedStageIndex !== null && steps[selectedStageIndex]) {
      const step = steps[selectedStageIndex];
      if (step.status === 'completed') {
        return findGlbArtifact(step);
      }
    }

    const completedSteps = steps.filter((s) => s.status === 'completed');
    for (let i = completedSteps.length - 1; i >= 0; i--) {
      const url = findGlbArtifact(completedSteps[i]);
      if (url) return url;
    }

    return null;
  },

  getCurrentImageUrls: () => {
    const { currentRun, steps, selectedStageIndex } = get();

    if (!currentRun || currentRun.status !== 'completed') {
      return [];
    }

    const toImageUrls = (step: PipelineStep): string[] =>
      step.outputArtifactIds
        .filter((id) => id.endsWith('.png') || id.endsWith('.jpg') || id.endsWith('.jpeg'))
        .map((id) => `/local-storage/${id}`);

    if (selectedStageIndex !== null && steps[selectedStageIndex]) {
      const step = steps[selectedStageIndex];
      if (step.status === 'completed') {
        const urls = toImageUrls(step);
        if (urls.length > 0) return urls;
      }
    }

    const completedSteps = steps.filter((s) => s.status === 'completed');
    const urls: string[] = [];
    completedSteps.forEach((step) => {
      urls.push(...toImageUrls(step));
    });

    return urls;
  },

  deletePipeline: async (pipelineId: string) => {
    await client.delete(`/api/v1/pipelines/${pipelineId}`);
    const { currentRun } = get();
    if (currentRun?.id === pipelineId) {
      stopPolling(set, get);
      set({ currentRun: null, steps: [], error: null, selectedStageIndex: null });
    }
  },

  retryPipeline: async (pipelineId: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await client.post(`/api/v1/pipelines/${pipelineId}/retry/1`);
      const pipeline = response.data as PipelineRun;
      set({ currentRun: pipeline, steps: pipeline.steps || [], isLoading: false });
      const retryId = setInterval(() => {
        const count = get()._pollCount + 1;
        if (count > MAX_POLL_COUNT) {
          stopPolling(set, get);
          set({ error: 'Pipeline timed out (no progress for 5 minutes)' });
          return;
        }
        set({ _pollCount: count });
        get().pollStatus(pipeline.id);
      }, 2000);
      set({ _pollIntervalId: retryId, _pollCount: 0 });
    } catch (err) {
      set({ isLoading: false, error: 'Failed to retry pipeline' });
      throw err;
    }
  },

  resumePipeline: async (pipelineId: string, selectedImageIndex: number) => {
    set({ isLoading: true, error: null });
    try {
      const response = await client.post(
        `/api/v1/pipelines/${pipelineId}/resume?selected_image_index=${selectedImageIndex}`
      );
      const pipeline = response.data as PipelineRun;
      set({ currentRun: pipeline, steps: pipeline.steps || [], isLoading: false });
      const intervalId = setInterval(() => {
        const count = get()._pollCount + 1;
        if (count > MAX_POLL_COUNT) {
          stopPolling(set, get);
          set({ error: 'Pipeline timed out (no progress for 5 minutes)' });
          return;
        }
        set({ _pollCount: count });
        get().pollStatus(pipeline.id);
      }, 2000);
      set({ _pollIntervalId: intervalId, _pollCount: 0 });
    } catch (err) {
      set({ isLoading: false, error: 'Failed to resume pipeline' });
      throw err;
    }
  },
}));