import { create } from 'zustand';
import client from '../api/client';
import type {
  ProviderSetting,
  ProviderSettingsResponse,
  ProviderSettingUpdate,
  PipelineTypeStageDefinitions,
  PipelineDefaultUpdate,
} from '../types/providerSettings';

interface ProviderSettingsState {
  settings: ProviderSetting[];
  defaults: Record<string, string>;
  pipelineTypeStageDefinitions: PipelineTypeStageDefinitions[];
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  fetchSettings: (showLoading?: boolean) => Promise<void>;
  updateSetting: (pipelineType: string, stage: string, update: ProviderSettingUpdate) => Promise<void>;
  updatePipelineDefault: (pipelineType: string, defaultMode: string) => Promise<void>;
}

export const useProviderSettingsStore = create<ProviderSettingsState>((set, get) => ({
  settings: [],
  defaults: {},
  pipelineTypeStageDefinitions: [],
  isLoading: false,
  isSaving: false,
  error: null,

  fetchSettings: async (showLoading = true) => {
    if (showLoading) {
      set({ isLoading: true, error: null });
    }
    try {
      const response = await client.get<ProviderSettingsResponse>('/api/v1/settings/providers');
      const rawDefaults = response.data.defaults;
      const convertedDefaults: Record<string, string> = {};
      for (const key in rawDefaults) {
        if (Object.prototype.hasOwnProperty.call(rawDefaults, key)) {
          const snakeKey = key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
          convertedDefaults[snakeKey] = rawDefaults[key];
        }
      }
      set({
        settings: response.data.settings,
        defaults: convertedDefaults,
        pipelineTypeStageDefinitions: response.data.stageDefinitions,
        isLoading: false,
      });
    } catch {
      set({ isLoading: false, error: 'Failed to load provider settings' });
    }
  },

  updateSetting: async (pipelineType: string, stage: string, update: ProviderSettingUpdate) => {
    set({ isSaving: true, error: null });
    try {
      await client.put(`/api/v1/settings/providers/${pipelineType}/${stage}`, update);
      await get().fetchSettings(false);
      set({ isSaving: false });
    } catch {
      set({ isSaving: false, error: 'Failed to save provider setting' });
    }
  },

  updatePipelineDefault: async (pipelineType: string, defaultMode: string) => {
    set({ isSaving: true, error: null });
    try {
      await client.put('/api/v1/settings/providers/defaults', { pipelineType, defaultMode } as PipelineDefaultUpdate);
      await get().fetchSettings(false);
      set({ isSaving: false });
    } catch {
      set({ isSaving: false, error: 'Failed to save pipeline default' });
    }
  },
}));