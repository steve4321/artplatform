import { useEffect, useState } from 'react';
import { useAuthStore } from '../stores/authStore';
import { useProviderSettingsStore } from '../stores/providerSettingsStore';
import type { StageDefinition, ProviderSetting, PipelineTypeStageDefinitions } from '../types/providerSettings';

const CLOUD_PROVIDER_LABELS: Record<string, string> = {
  stability_ai: 'Stability AI',
  fal_ai: 'fal.ai',
  replicate: 'Replicate',
  comfyui: 'ComfyUI',
  tripo_cloud: 'Tripo Cloud',
  meshy_ai: 'Meshy AI',
  csm_ai: 'CSM AI',
};

function getCloudProviderLabel(provider: string): string {
  return CLOUD_PROVIDER_LABELS[provider] || provider;
}

const DEFAULT_MODE_OPTIONS = [
  { value: 'cloud', label: '全部云端' },
  { value: 'local', label: '全部本机' },
  { value: 'mock', label: 'Mock' },
  { value: 'custom', label: '自定义' },
];

interface StageCardProps {
  stageDefinition: StageDefinition;
  setting: ProviderSetting | undefined;
  pipelineDefault: string;
  onSave: (payload: { mode: string; cloudProvider?: string | null; apiKey?: string | null; baseUrl?: string | null }) => void;
  onDefaultChange: (defaultMode: string) => void;
  isSaving: boolean;
  isSaved: boolean;
}

function StageCard({
  stageDefinition,
  setting,
  pipelineDefault,
  onSave,
  onDefaultChange,
  isSaving,
  isSaved,
}: StageCardProps) {
  const [localMode, setLocalMode] = useState(setting?.mode || 'mock');
  const [cloudProvider, setCloudProvider] = useState(setting?.cloudProvider || '');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState(setting?.baseUrl || '');
  const [showApiKey, setShowApiKey] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (setting) {
      setLocalMode(setting.mode);
      setCloudProvider(setting.cloudProvider || '');
      setBaseUrl(setting.baseUrl || '');
      setDirty(false);
    }
  }, [setting]);

  const selectedMode = stageDefinition.modes.find((m) => m.mode === localMode);
  const isCloudMode = localMode === 'cloud';
  const isSkipMode = localMode === 'skip';
  const isDefaultMode = localMode === pipelineDefault;
  const isOverridden = setting?.mode !== undefined && setting.mode !== pipelineDefault && localMode === pipelineDefault;

  const handleModeChange = (newMode: string) => {
    setLocalMode(newMode);
    setDirty(true);
    if (newMode !== pipelineDefault && pipelineDefault !== 'custom') {
      onDefaultChange('custom');
    }
  };

  const handleSave = () => {
    const payload: { mode: string; cloudProvider?: string | null; apiKey?: string | null; baseUrl?: string | null } = {
      mode: localMode,
    };
    if (isCloudMode) {
      payload.cloudProvider = cloudProvider || null;
      payload.apiKey = apiKey || null;
      payload.baseUrl = baseUrl || null;
    }
    onSave(payload);
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-gray-100">{stageDefinition.label}</h3>
          <p className="text-sm text-gray-500 mt-0.5">{stageDefinition.description}</p>
        </div>
        <div className="flex items-center gap-2">
          {isDefaultMode && (
            <span className="text-xs text-green-400">(默认)</span>
          )}
          {isOverridden && (
            <span className="text-xs text-yellow-400">(已覆盖)</span>
          )}
          <select
            value={localMode}
            onChange={(e) => handleModeChange(e.target.value)}
            className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 text-sm focus:outline-none focus:border-blue-600"
          >
            {stageDefinition.modes.map((mode) => (
              <option key={mode.mode} value={mode.mode}>
                {mode.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isCloudMode && (
        <div className="space-y-3 mt-4 pt-4 border-t border-gray-800">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Provider</label>
            <select
              value={cloudProvider}
              onChange={(e) => { setCloudProvider(e.target.value); setDirty(true); }}
              className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:border-blue-600"
            >
              <option value="">Select provider</option>
              {stageDefinition.cloudProviders.map((provider) => (
                <option key={provider} value={provider}>
                  {getCloudProviderLabel(provider)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">API Key</label>
            <div className="relative">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => { setApiKey(e.target.value); setDirty(true); }}
                placeholder="sk-..."
                className="w-full px-4 py-2 pr-10 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-600"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
              >
                {showApiKey ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.543 7-1.275 4.057-5.065 7-9.543 7-4.477 0-8.268-2.943-9.543-7z" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">
              Base URL <span className="text-gray-600">(optional)</span>
            </label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => { setBaseUrl(e.target.value); setDirty(true); }}
              placeholder="https://api.example.com"
              className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-600"
            />
          </div>
        </div>
      )}

      {isSkipMode && (
        <div className="mt-4 pt-4 border-t border-gray-800">
          <p className="text-sm text-gray-400">
            Current: <span className="text-gray-200">{selectedMode?.label || localMode}</span>
          </p>
        </div>
      )}

      {!isCloudMode && !isSkipMode && (
        <div className="mt-4 pt-4 border-t border-gray-800">
          <p className="text-sm text-gray-400">
            Current: <span className="text-gray-200">{selectedMode?.label || localMode}</span>
          </p>
        </div>
      )}

      <div className="mt-4 flex items-center justify-end gap-3">
        {isSaving && (
          <span className="text-sm text-gray-500">Saving...</span>
        )}
        {isSaved && (
          <span className="text-sm text-green-400 flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Saved
          </span>
        )}
        <button
          onClick={handleSave}
          disabled={isSaving || !dirty}
          className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
        >
          Save
        </button>
      </div>
    </div>
  );
}

interface PipelineSectionProps {
  pipelineType: PipelineTypeStageDefinitions;
  settings: ProviderSetting[];
  defaults: Record<string, string>;
  onSave: (pipelineType: string, stage: string, payload: { mode: string; cloudProvider?: string | null; apiKey?: string | null; baseUrl?: string | null }) => void;
  onDefaultChange: (pipelineType: string, defaultMode: string) => void;
  saveStatus: Record<string, 'idle' | 'saving' | 'saved'>;
  isSaving: boolean;
}

function PipelineSection({
  pipelineType,
  settings,
  defaults,
  onSave,
  onDefaultChange,
  saveStatus,
  isSaving,
}: PipelineSectionProps) {
  const pipelineDefault = defaults[pipelineType.pipelineType] || 'cloud';

  const getSettingForStage = (stage: string): ProviderSetting | undefined => {
    return settings.find((s) => s.pipelineType === pipelineType.pipelineType && s.stage === stage);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <h3 className="text-lg font-semibold text-gray-100">{pipelineType.label}</h3>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">默认模式:</label>
          <select
            value={pipelineDefault}
            onChange={(e) => onDefaultChange(pipelineType.pipelineType, e.target.value)}
            className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 text-sm focus:outline-none focus:border-blue-600"
          >
            {DEFAULT_MODE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="grid gap-4">
        {pipelineType.stages.map((stageDef) => (
          <StageCard
            key={stageDef.stage}
            stageDefinition={stageDef}
            setting={getSettingForStage(stageDef.stage)}
            pipelineDefault={pipelineDefault}
            onSave={(payload) => onSave(pipelineType.pipelineType, stageDef.stage, payload)}
            onDefaultChange={(defaultMode) => onDefaultChange(pipelineType.pipelineType, defaultMode)}
            isSaving={isSaving}
            isSaved={saveStatus[`${pipelineType.pipelineType}:${stageDef.stage}`] === 'saved'}
          />
        ))}
      </div>
    </div>
  );
}

function SettingsPage() {
  const { user } = useAuthStore();
  const {
    settings,
    defaults,
    pipelineTypeStageDefinitions,
    isLoading,
    error,
    fetchSettings,
    updateSetting,
    updatePipelineDefault,
  } = useProviderSettingsStore();

  const [saveStatus, setSaveStatus] = useState<Record<string, 'idle' | 'saving' | 'saved'>>({});

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const handleSave = async (
    pipelineType: string,
    stage: string,
    payload: { mode: string; cloudProvider?: string | null; apiKey?: string | null; baseUrl?: string | null }
  ) => {
    const key = `${pipelineType}:${stage}`;
    setSaveStatus((prev) => ({ ...prev, [key]: 'saving' }));
    try {
      await updateSetting(pipelineType, stage, payload);
      setSaveStatus((prev) => ({ ...prev, [key]: 'saved' }));
      setTimeout(() => {
        setSaveStatus((prev) => ({ ...prev, [key]: 'idle' }));
      }, 2000);
    } catch {
      setSaveStatus((prev) => ({ ...prev, [key]: 'idle' }));
    }
  };

  const handleDefaultChange = async (pipelineType: string, defaultMode: string) => {
    try {
      await updatePipelineDefault(pipelineType, defaultMode);
    } catch {
      // error handled in store
    }
  };

  if (!user) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Settings</h1>
          <p className="text-gray-400 mt-1">Configure your workspace</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center">
          <p className="text-gray-500">Loading user info...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Settings</h1>
        <p className="text-gray-400 mt-1">Configure your workspace</p>
      </div>

      {/* Account */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg divide-y divide-gray-800">
        <div className="p-6">
          <h2 className="text-lg font-semibold text-gray-100">Account</h2>
          <div className="mt-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-400">Email</label>
              <p className="mt-1 w-full max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100">
                {user.email}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-400">Display Name</label>
              <p className="mt-1 w-full max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100">
                {user.displayName}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-400">Role</label>
              <span className="mt-1 inline-block px-3 py-1 bg-blue-900/50 text-blue-400 text-sm font-medium rounded-full">
                {user.role}
              </span>
            </div>
            {user.teamId && (
              <div>
                <label className="block text-sm font-medium text-gray-400">Team ID</label>
                <p className="mt-1 w-full max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 font-mono text-sm">
                  {user.teamId}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div>
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-gray-100">Pipeline Providers</h2>
          <p className="text-sm text-gray-500 mt-1">Configure AI providers for each pipeline stage</p>
        </div>

        {isLoading ? (
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center">
            <p className="text-gray-500">Loading provider settings...</p>
          </div>
        ) : error ? (
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center">
            <p className="text-red-400">{error}</p>
          </div>
        ) : (
          <div className="space-y-8">
            {pipelineTypeStageDefinitions.map((pipelineType) => (
              <PipelineSection
                key={pipelineType.pipelineType}
                pipelineType={pipelineType}
                settings={settings}
                defaults={defaults}
                onSave={handleSave}
                onDefaultChange={handleDefaultChange}
                saveStatus={saveStatus}
                isSaving={false}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default SettingsPage;
