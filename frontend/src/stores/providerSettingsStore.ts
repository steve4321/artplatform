import { create } from 'zustand';
import client from '../api/client';
import type {
  ProviderSetting,
  ProviderSettingsResponse,
  ProviderSettingUpdate,
  StageDefinition,
} from '../types/providerSettings';

interface ProviderSettingsState {
  settings: ProviderSetting[];
  stageDefinitions: StageDefinition[];
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  fetchSettings: () => Promise<void>;
  updateSetting: (stage: string, update: ProviderSettingUpdate) => Promise<void>;
}

export const useProviderSettingsStore = create<ProviderSettingsState>((set, get) => ({
  settings: [],
  stageDefinitions: [],
  isLoading: false,
  isSaving: false,
  error: null,

  fetchSettings: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await client.get<ProviderSettingsResponse>('/api/v1/settings/providers');
      set({
        settings: response.data.settings,
        stageDefinitions: response.data.stageDefinitions,
        isLoading: false,
      });
    } catch {
      set({ isLoading: false, error: 'Failed to load provider settings' });
    }
  },

  updateSetting: async (stage: string, update: ProviderSettingUpdate) => {
    set({ isSaving: true, error: null });
    try {
      await client.put(`/api/v1/settings/providers/${stage}`, update);
      await get().fetchSettings();
      set({ isSaving: false });
    } catch {
      set({ isSaving: false, error: 'Failed to save provider setting' });
    }
  },
}));