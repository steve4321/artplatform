import { create } from 'zustand';
import client from '../api/client';

export type PipelineStatus = 'pending' | 'running' | 'completed' | 'failed';
export type StepStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface PipelineStep {
  id: string;
  stage: string;
  status: StepStatus;
  startedAt: string | null;
  completedAt: string | null;
  error: string | null;
  outputUrl?: string | null;
  durationMs?: number;
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
  wsConnection: WebSocket | null;
  selectedStageIndex: number | null;
  startPipeline: (prompt: string, negativePrompt?: string, stylePreset?: string, quality?: string) => Promise<void>;
  fetchCurrentRun: () => Promise<void>;
  resetPipeline: () => void;
  connectWebSocket: (pipelineId: string) => void;
  disconnectWebSocket: () => void;
  selectStage: (index: number | null) => void;
  getCurrentModelUrl: () => string | null;
}

const PIPELINE_STAGES = [
  'text_to_image',
  '3d_generate',
  'cleanup',
  'uv_material',
  'rig',
  'animate',
];

export const usePipelineStore = create<PipelineState>((set, get) => ({
  currentRun: null,
  steps: [],
  isLoading: false,
  error: null,
  wsConnection: null,
  selectedStageIndex: null,

  startPipeline: async (prompt: string, negativePrompt?: string, stylePreset?: string, quality?: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await client.post('/api/v1/pipelines', {
        prompt,
        negative_prompt: negativePrompt,
        style_preset: stylePreset || 'realistic',
        quality: quality || 'standard',
      });
      const pipelineId = response.data.id;

      const initialSteps: PipelineStep[] = PIPELINE_STAGES.map((stage) => ({
        id: `${pipelineId}-${stage}`,
        stage,
        status: 'pending' as StepStatus,
        startedAt: null,
        completedAt: null,
        error: null,
        outputUrl: null,
        durationMs: undefined,
      }));

      const run: PipelineRun = {
        id: pipelineId,
        prompt,
        status: 'running',
        steps: initialSteps,
        createdAt: new Date().toISOString(),
        completedAt: null,
        error: null,
      };

      set({ currentRun: run, steps: initialSteps, isLoading: false });
      get().connectWebSocket(pipelineId);
    } catch (err) {
      set({ isLoading: false, error: 'Failed to start pipeline' });
      throw err;
    }
  },

  fetchCurrentRun: async () => {
    set({ isLoading: true });
    try {
      const response = await client.get('/api/v1/pipelines/current');
      if (response.data) {
        set({ currentRun: response.data, steps: response.data.steps || [] });
      }
      set({ isLoading: false });
    } catch {
      set({ isLoading: false, error: 'Failed to fetch pipeline' });
    }
  },

  resetPipeline: () => {
    const { wsConnection } = get();
    if (wsConnection) {
      wsConnection.close();
    }
    set({ currentRun: null, steps: [], error: null, wsConnection: null, selectedStageIndex: null });
  },

  connectWebSocket: (pipelineId: string) => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host;
    const wsUrl = `${wsProtocol}//${wsHost}/api/v1/pipelines/${pipelineId}/ws`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const { steps } = get();

        if (data.stage) {
          const stageIndex = PIPELINE_STAGES.indexOf(data.stage);
          if (stageIndex !== -1) {
            const updatedSteps = [...steps];
            const step = updatedSteps[stageIndex];

            if (data.status === 'running' && step.status === 'pending') {
              updatedSteps[stageIndex] = {
                ...step,
                status: 'running',
                startedAt: new Date().toISOString(),
              };
            } else if (data.status === 'completed') {
              updatedSteps[stageIndex] = {
                ...step,
                status: 'completed',
                completedAt: new Date().toISOString(),
                outputUrl: data.output_url || null,
                durationMs: data.duration_ms || null,
              };
            } else if (data.status === 'failed') {
              updatedSteps[stageIndex] = {
                ...step,
                status: 'failed',
                completedAt: new Date().toISOString(),
                error: data.error || 'Unknown error',
              };
            }

            const allCompleted = updatedSteps.every((s) => s.status === 'completed');
            const anyFailed = updatedSteps.some((s) => s.status === 'failed');

            set({
              steps: updatedSteps,
              currentRun: get().currentRun
                ? {
                    ...get().currentRun!,
                    status: allCompleted ? 'completed' : anyFailed ? 'failed' : 'running',
                    completedAt: allCompleted || anyFailed ? new Date().toISOString() : null,
                  }
                : null,
            });
          }
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      set({ error: 'WebSocket connection error' });
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
    };

    set({ wsConnection: ws });
  },

  disconnectWebSocket: () => {
    const { wsConnection } = get();
    if (wsConnection) {
      wsConnection.close();
      set({ wsConnection: null });
    }
  },

  selectStage: (index: number | null) => {
    set({ selectedStageIndex: index });
  },

  getCurrentModelUrl: () => {
    const { steps, selectedStageIndex } = get();
    if (selectedStageIndex !== null && steps[selectedStageIndex]) {
      return steps[selectedStageIndex].outputUrl ?? null;
    }
    const completedSteps = steps.filter((s) => s.status === 'completed');
    if (completedSteps.length > 0) {
      return completedSteps[completedSteps.length - 1].outputUrl ?? null;
    }
    return null;
  },
}));