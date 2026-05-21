export interface StageModeOption {
  mode: string;
  label: string;
  processorName: string;
}

export interface StageDefinition {
  stage: string;
  label: string;
  description: string;
  modes: StageModeOption[];
  cloudProviders: string[];
}

export interface ProviderSetting {
  id: string | null;
  stage: string;
  mode: string;
  processorName: string;
  cloudProvider: string | null;
  apiKey: string | null;
  baseUrl: string | null;
  extraConfig: Record<string, unknown> | null;
  updatedAt: string | null;
}

export interface ProviderSettingsResponse {
  settings: ProviderSetting[];
  stageDefinitions: StageDefinition[];
}

export interface ProviderSettingUpdate {
  mode: string;
  cloudProvider?: string | null;
  apiKey?: string | null;
  baseUrl?: string | null;
  extraConfig?: Record<string, unknown> | null;
}