import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { AssetViewer } from '../components/viewer';
import { usePipelineStore, PipelineStep } from '../stores/pipelineStore';
import type { StylePreset, QualityLevel, PipelineType, UsageType, OutputSize, OutputFormat } from '../types';

type StageConfig = {
  id: string;
  name: string;
  icon: string;
};

const PIPELINE_STAGES_3D: StageConfig[] = [
  { id: 'text_to_image', name: 'Text → Image', icon: '🖼' },
  { id: '3d_generate', name: '3D Generate', icon: '📦' },
  { id: 'cleanup', name: 'Cleanup', icon: '🧹' },
  { id: 'uv_material', name: 'UV+Material', icon: '🎨' },
  { id: 'rig', name: 'Rig', icon: '🦴' },
  { id: 'animate', name: 'Animate', icon: '🎬' },
];

const PIPELINE_STAGES_2D: StageConfig[] = [
  { id: 'text_to_image', name: 'Text → Image', icon: '🖼' },
  { id: 'postprocess_2d', name: 'Post-Process', icon: '✂️' },
  { id: 'format_output_2d', name: 'Format Output', icon: '📄' },
];

const STYLE_PRESETS: { value: StylePreset; label: string }[] = [
  { value: 'realistic', label: 'Realistic' },
  { value: 'anime', label: 'Anime' },
  { value: 'cartoon', label: 'Cartoon' },
  { value: 'fantasy', label: 'Fantasy' },
  { value: 'sci-fi', label: 'Sci-Fi' },
];

const USAGE_TYPES: { value: UsageType; label: string }[] = [
  { value: 'icon', label: 'Icon' },
  { value: 'portrait', label: 'Portrait' },
  { value: 'card', label: 'Card' },
  { value: 'background', label: 'Background' },
  { value: 'sprite', label: 'Sprite' },
];

const OUTPUT_SIZES: { value: OutputSize; label: string }[] = [
  { value: '64x64', label: '64' },
  { value: '128x128', label: '128' },
  { value: '256x256', label: '256' },
  { value: '512x512', label: '512' },
  { value: '1024x1024', label: '1024' },
];

const OUTPUT_FORMATS: { value: OutputFormat; label: string }[] = [
  { value: 'png', label: 'PNG' },
  { value: 'sprite_sheet', label: 'Sprite' },
  { value: '9_patch', label: '9-Patch' },
];

/* ─── Status Banner ─── */
function StatusBanner({
  status,
  currentStageName,
  progress,
  elapsed,
}: {
  status: 'idle' | 'loading' | 'running' | 'completed' | 'failed';
  currentStageName?: string;
  progress: number;
  elapsed: number;
}) {
  if (status === 'idle') return null;

  const colors: Record<string, string> = {
    loading: 'bg-blue-900/60 border-blue-700',
    running: 'bg-blue-900/60 border-blue-700',
    completed: 'bg-green-900/60 border-green-700',
    failed: 'bg-red-900/60 border-red-700',
  };

  const labels: Record<string, string> = {
    loading: 'Starting pipeline…',
    running: currentStageName ? `Processing: ${currentStageName}` : 'Running…',
    completed: 'Pipeline completed',
    failed: 'Pipeline failed',
  };

  const elapsedStr = elapsed > 0 ? `${(elapsed / 1000).toFixed(1)}s` : '';

  return (
    <div className={`px-4 py-2 border-b flex items-center gap-3 text-sm ${colors[status]}`}>
      {(status === 'loading' || status === 'running') && (
        <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin flex-shrink-0" />
      )}
      {status === 'completed' && <span className="text-green-400">✓</span>}
      {status === 'failed' && <span className="text-red-400">✗</span>}

      <span className="text-gray-200 flex-1 truncate">{labels[status]}</span>

      {elapsedStr && <span className="text-gray-400 text-xs flex-shrink-0">{elapsedStr}</span>}

      {(status === 'loading' || status === 'running') && (
        <div className="w-24 h-1.5 bg-gray-700 rounded-full overflow-hidden flex-shrink-0">
          <div
            className="h-full bg-blue-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}

/* ─── StageIcon ─── */
function StageIcon({ stage, status }: { stage: StageConfig; status: string }) {
  const statusStyles: Record<string, string> = {
    pending: 'text-gray-600',
    running: 'text-blue-500 animate-pulse',
    completed: 'text-green-500',
    failed: 'text-red-500',
  };

  const statusSymbols: Record<string, string> = {
    pending: '○',
    running: '◉',
    completed: '✓',
    failed: '✗',
  };

  return (
    <div className={`text-lg ${statusStyles[status] || 'text-gray-600'}`}>
      {status === 'pending' ? stage.icon : statusSymbols[status] || stage.icon}
    </div>
  );
}

/* ─── Pipeline Timeline ─── */
function PipelineTimeline({
  steps,
  selectedIndex,
  onSelectStage,
  pipelineType,
  isRunning,
  onRetry,
  onDiscard,
}: {
  steps: PipelineStep[];
  selectedIndex: number | null;
  onSelectStage: (index: number | null) => void;
  pipelineType: PipelineType;
  isRunning: boolean;
  onRetry: () => void;
  onDiscard: () => void;
}) {
  const stages = pipelineType === '2d_art' ? PIPELINE_STAGES_2D : PIPELINE_STAGES_3D;

  const overallProgress = useMemo(() => {
    if (steps.length === 0) return 0;
    const completed = steps.filter((s) => s.status === 'completed' || s.status === 'failed').length;
    return (completed / stages.length) * 100;
  }, [steps, stages.length]);

  const hasRunning = steps.some((s) => s.status === 'running');

  return (
    <div className="h-full flex flex-col">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Timeline</h3>

      <div className="mb-3">
        <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
          <span>Progress</span>
          <span>{Math.round(overallProgress)}%</span>
        </div>
        <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ${
              hasRunning ? 'bg-blue-600 animate-pulse' : 'bg-green-600'
            }`}
            style={{ width: `${overallProgress}%` }}
          />
        </div>
      </div>

      <div className="flex-1 space-y-1.5 overflow-y-auto">
        {stages.map((stage, index) => {
          const step = steps[index];
          const status = step?.status || 'pending';
          const duration = step?.durationMs;
          const error = step?.errorMessage;
          const isSelected = selectedIndex === index;
          const isClickable = status === 'completed' || status === 'failed';

          return (
            <button
              key={stage.id}
              onClick={() => isClickable && onSelectStage(isClickable ? (isSelected ? null : index) : null)}
              disabled={!isClickable}
              className={`w-full flex items-center gap-2 p-2 rounded-md transition-all text-left ${
                isSelected
                  ? 'bg-blue-900/30 border border-blue-700'
                  : isClickable
                  ? 'bg-gray-800/50 border border-gray-700 hover:border-gray-600 hover:bg-gray-800'
                  : 'bg-gray-900 border border-gray-800'
              }`}
            >
              <StageIcon stage={stage} status={status} />
              <div className="flex-1 min-w-0">
                <p className={`text-xs font-medium truncate ${status === 'pending' ? 'text-gray-500' : 'text-gray-200'}`}>
                  {stage.name}
                </p>
                <div className="flex items-center gap-2">
                  {duration ? (
                    <span className="text-[10px] text-gray-500">{(duration / 1000).toFixed(1)}s</span>
                  ) : null}
                  {error && status === 'failed' && (
                    <span className="text-[10px] text-red-400 truncate">{error}</span>
                  )}
                </div>
              </div>
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded-full flex-shrink-0 ${
                  status === 'completed'
                    ? 'bg-green-900/50 text-green-400'
                    : status === 'running'
                    ? 'bg-blue-900/50 text-blue-400'
                    : status === 'failed'
                    ? 'bg-red-900/50 text-red-400'
                    : 'bg-gray-800 text-gray-500'
                }`}
              >
                {status}
              </span>
            </button>
          );
        })}
      </div>

      {steps.length > 0 && steps.some((s) => s.status === 'failed') && (
        <div className="mt-3 flex gap-2">
          <button
            onClick={onRetry}
            disabled={isRunning}
            className="flex-1 py-1.5 bg-red-600 hover:bg-red-700 disabled:opacity-40 text-white text-xs font-medium rounded-md transition-colors"
          >
            Retry
          </button>
          <button
            onClick={onDiscard}
            disabled={isRunning}
            className="flex-1 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-gray-300 text-xs font-medium rounded-md transition-colors"
          >
            Discard
          </button>
        </div>
      )}
    </div>
  );
}

/* ─── Config Panel 3D ─── */
function ConfigPanel3D({
  prompt,
  onPromptChange,
  negativePrompt,
  onNegativePromptChange,
  stylePreset,
  onStylePresetChange,
  quality,
  onQualityChange,
  onGenerate,
  isBusy,
  referenceFile,
  onReferenceFileChange,
}: {
  prompt: string;
  onPromptChange: (v: string) => void;
  negativePrompt: string;
  onNegativePromptChange: (v: string) => void;
  stylePreset: StylePreset;
  onStylePresetChange: (v: StylePreset) => void;
  quality: QualityLevel;
  onQualityChange: (v: QualityLevel) => void;
  onGenerate: () => void;
  isBusy: boolean;
  referenceFile: File | null;
  onReferenceFileChange: (file: File | null) => void;
}) {
  const [showNegative, setShowNegative] = useState(false);

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">
          Prompt <span className="text-red-500">*</span>
        </label>
        <textarea
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          placeholder="A medieval warrior with sword and shield, PBR textures..."
          rows={4}
          className="w-full px-3 py-2 text-sm bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-600 resize-none"
        />
        <p className="mt-1 text-[10px] text-gray-600">{prompt.length} / 10 min</p>
      </div>

      <div>
        <button
          type="button"
          onClick={() => setShowNegative(!showNegative)}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-300 transition-colors"
        >
          <svg
            className={`w-3 h-3 transition-transform ${showNegative ? 'rotate-90' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          Negative Prompt
        </button>
        {showNegative && (
          <textarea
            value={negativePrompt}
            onChange={(e) => onNegativePromptChange(e.target.value)}
            placeholder="Blurry, low quality, distorted..."
            rows={2}
            className="mt-1.5 w-full px-3 py-2 text-sm bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-600 resize-none"
          />
        )}
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">Style</label>
        <select
          value={stylePreset}
          onChange={(e) => onStylePresetChange(e.target.value as StylePreset)}
          className="w-full px-3 py-2 text-sm bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:border-blue-600"
        >
          {STYLE_PRESETS.map((preset) => (
            <option key={preset.value} value={preset.value}>
              {preset.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">Quality</label>
        <div className="flex gap-1.5">
          {(['draft', 'standard', 'high'] as QualityLevel[]).map((q) => (
            <button
              key={q}
              onClick={() => onQualityChange(q)}
              disabled={isBusy}
              className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-colors ${
                quality === q
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {q.charAt(0).toUpperCase() + q.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">Reference (optional)</label>
        {referenceFile ? (
          <div className="flex items-center gap-2">
            <span className="flex-1 text-xs text-gray-300 truncate bg-gray-800 px-3 py-2 rounded-md">{referenceFile.name}</span>
            <button
              onClick={() => onReferenceFileChange(null)}
              disabled={isBusy}
              className="p-2 text-gray-500 hover:text-red-400 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        ) : (
          <label className="w-full py-2 border border-dashed border-gray-700 rounded-md text-gray-500 hover:border-gray-600 hover:text-gray-400 transition-colors flex items-center justify-center gap-1.5 text-xs cursor-pointer">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
            Upload
            <input
              type="file"
              accept="image/*"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onReferenceFileChange(f);
              }}
              className="hidden"
            />
          </label>
        )}
      </div>

      <button
        onClick={onGenerate}
        disabled={prompt.length < 10 || isBusy}
        className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
      >
        {isBusy ? (
          <>
            <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Generating…
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
            Generate
          </>
        )}
      </button>
    </div>
  );
}

/* ─── Config Panel 2D ─── */
function ConfigPanel2D({
  prompt,
  onPromptChange,
  negativePrompt,
  onNegativePromptChange,
  stylePreset,
  onStylePresetChange,
  usageType,
  onUsageTypeChange,
  outputSize,
  onOutputSizeChange,
  removeBackground,
  onRemoveBackgroundChange,
  outputFormat,
  onOutputFormatChange,
  onGenerate,
  isBusy,
}: {
  prompt: string;
  onPromptChange: (v: string) => void;
  negativePrompt: string;
  onNegativePromptChange: (v: string) => void;
  stylePreset: StylePreset;
  onStylePresetChange: (v: StylePreset) => void;
  usageType: UsageType;
  onUsageTypeChange: (v: UsageType) => void;
  outputSize: OutputSize;
  onOutputSizeChange: (v: OutputSize) => void;
  removeBackground: boolean;
  onRemoveBackgroundChange: (v: boolean) => void;
  outputFormat: OutputFormat;
  onOutputFormatChange: (v: OutputFormat) => void;
  onGenerate: () => void;
  isBusy: boolean;
}) {
  const [showNegative, setShowNegative] = useState(false);

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">
          Prompt <span className="text-red-500">*</span>
        </label>
        <textarea
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          placeholder="A burning legendary sword icon, dark fantasy style..."
          rows={3}
          className="w-full px-3 py-2 text-sm bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-600 resize-none"
        />
        <p className="mt-1 text-[10px] text-gray-600">{prompt.length} / 10 min</p>
      </div>

      <div>
        <button
          type="button"
          onClick={() => setShowNegative(!showNegative)}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-300 transition-colors"
        >
          <svg
            className={`w-3 h-3 transition-transform ${showNegative ? 'rotate-90' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          Negative Prompt
        </button>
        {showNegative && (
          <textarea
            value={negativePrompt}
            onChange={(e) => onNegativePromptChange(e.target.value)}
            placeholder="Blurry, low quality, white background..."
            rows={2}
            className="mt-1.5 w-full px-3 py-2 text-sm bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-600 resize-none"
          />
        )}
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">Style</label>
        <select
          value={stylePreset}
          onChange={(e) => onStylePresetChange(e.target.value as StylePreset)}
          className="w-full px-3 py-2 text-sm bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:border-blue-600"
        >
          {STYLE_PRESETS.map((preset) => (
            <option key={preset.value} value={preset.value}>
              {preset.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">Usage</label>
        <div className="grid grid-cols-3 gap-1.5">
          {USAGE_TYPES.map((t) => (
            <button
              key={t.value}
              onClick={() => onUsageTypeChange(t.value)}
              disabled={isBusy}
              className={`py-1.5 rounded-md text-xs font-medium transition-colors ${
                usageType === t.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">Size (px)</label>
        <div className="grid grid-cols-5 gap-1">
          {OUTPUT_SIZES.map((s) => (
            <button
              key={s.value}
              onClick={() => onOutputSizeChange(s.value)}
              disabled={isBusy}
              className={`py-1.5 rounded-md text-xs font-medium transition-colors ${
                outputSize === s.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">Background</label>
        <div className="flex gap-1.5">
          <button
            onClick={() => onRemoveBackgroundChange(true)}
            disabled={isBusy}
            className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-colors ${
              removeBackground ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            Remove
          </button>
          <button
            onClick={() => onRemoveBackgroundChange(false)}
            disabled={isBusy}
            className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-colors ${
              !removeBackground ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            Keep
          </button>
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">Format</label>
        <div className="flex gap-1.5">
          {OUTPUT_FORMATS.map((f) => (
            <button
              key={f.value}
              onClick={() => onOutputFormatChange(f.value)}
              disabled={isBusy}
              className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-colors ${
                outputFormat === f.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <button
        onClick={onGenerate}
        disabled={prompt.length < 10 || isBusy}
        className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
      >
        {isBusy ? (
          <>
            <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Generating…
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
            Generate
          </>
        )}
      </button>
    </div>
  );
}

/* ─── Preview 3D ─── */
function PreviewPanel3D({
  modelUrl,
  currentStep,
}: {
  modelUrl: string | null;
  currentStep: number;
}) {
  const stepNames = PIPELINE_STAGES_3D.map((s) => s.name);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden h-full flex flex-col">
      <div className="px-3 py-2 border-b border-gray-800 flex items-center justify-between">
        <h3 className="text-xs font-medium text-gray-400">3D Preview</h3>
        {currentStep >= 0 && (
          <span className="text-[10px] text-gray-500">
            {stepNames[currentStep] || 'Final'}
          </span>
        )}
      </div>
      <div className="flex-1 relative">
        {modelUrl ? (
          <AssetViewer modelUrl={modelUrl} className="w-full h-full" autoPlay />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-600">
            <svg className="w-16 h-16 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
              />
            </svg>
            <p className="text-sm text-gray-500">No model loaded</p>
            <p className="text-xs text-gray-600 mt-1">Enter a prompt and click Generate</p>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Preview 2D ─── */
function PreviewPanel2D({
  imageUrls,
  currentStep,
}: {
  imageUrls: string[];
  currentStep: number;
}) {
  const stepNames = PIPELINE_STAGES_2D.map((s) => s.name);
  const isFinalOutput = currentStep === PIPELINE_STAGES_2D.length - 1 || currentStep < 0;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden h-full flex flex-col">
      <div className="px-3 py-2 border-b border-gray-800 flex items-center justify-between">
        <h3 className="text-xs font-medium text-gray-400">2D Preview</h3>
        {currentStep >= 0 && (
          <span className="text-[10px] text-gray-500">
            {isFinalOutput ? 'Output' : stepNames[currentStep]}
          </span>
        )}
      </div>
      <div className="flex-1 relative overflow-auto">
        {imageUrls.length > 0 ? (
          isFinalOutput ? (
            <div className="w-full h-full flex items-center justify-center p-4">
              <div
                className="relative max-w-full max-h-full"
                style={{
                  backgroundImage: `
                    linear-gradient(45deg, #374151 25%, transparent 25%),
                    linear-gradient(-45deg, #374151 25%, transparent 25%),
                    linear-gradient(45deg, transparent 75%, #374151 75%),
                    linear-gradient(-45deg, transparent 75%, #374151 75%)
                  `,
                  backgroundSize: '20px 20px',
                  backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px',
                }}
              >
                <img
                  src={imageUrls[0]}
                  alt="Generated art"
                  className="max-w-[512px] max-h-[512px] w-auto h-auto object-contain"
                />
              </div>
            </div>
          ) : (
            <div className="p-4 grid grid-cols-2 gap-3">
              {imageUrls.slice(0, 4).map((url, idx) => (
                <div
                  key={idx}
                  className="relative aspect-square bg-gray-800 rounded-lg overflow-hidden"
                  style={{
                    backgroundImage: `
                      linear-gradient(45deg, #1f2937 25%, transparent 25%),
                      linear-gradient(-45deg, #1f2937 25%, transparent 25%),
                      linear-gradient(45deg, transparent 75%, #1f2937 75%),
                      linear-gradient(-45deg, transparent 75%, #1f2937 75%)
                    `,
                    backgroundSize: '16px 16px',
                    backgroundPosition: '0 0, 0 8px, 8px -8px, -8px 0px',
                  }}
                >
                  <img src={url} alt={`Candidate ${idx + 1}`} className="w-full h-full object-contain" />
                </div>
              ))}
            </div>
          )
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-600">
            <svg className="w-16 h-16 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
            <p className="text-sm text-gray-500">No images generated</p>
            <p className="text-xs text-gray-600 mt-1">Enter a prompt and click Generate</p>
          </div>
        )}
      </div>
      {imageUrls.length > 0 && (
        <div className="px-3 py-1.5 border-t border-gray-800 text-[10px] text-gray-500">
          {imageUrls.length} image{imageUrls.length !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
}

/* ─── Action Bar 3D ─── */
function ActionBar3D({
  modelUrl,
  isBusy,
}: {
  modelUrl: string | null;
  isBusy: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        disabled={!modelUrl || isBusy}
        className="flex-1 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed text-gray-200 text-xs font-medium rounded-md transition-colors flex items-center justify-center gap-1.5"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
        FBX
      </button>
      <button
        disabled={!modelUrl || isBusy}
        className="flex-1 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed text-gray-200 text-xs font-medium rounded-md transition-colors flex items-center justify-center gap-1.5"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
        GLB
      </button>
      <button
        disabled={!modelUrl || isBusy}
        className="flex-1 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-medium rounded-md transition-colors flex items-center justify-center gap-1.5"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
        Review
      </button>
    </div>
  );
}

/* ─── Action Bar 2D ─── */
function ActionBar2D({
  imageUrls,
  outputFormat,
  isBusy,
}: {
  imageUrls: string[];
  outputFormat: OutputFormat;
  isBusy: boolean;
}) {
  const hasOutput = imageUrls.length > 0;

  return (
    <div className="flex items-center gap-2">
      <button
        disabled={!hasOutput || isBusy}
        className="flex-1 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed text-gray-200 text-xs font-medium rounded-md transition-colors flex items-center justify-center gap-1.5"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
        PNG
      </button>
      {outputFormat === 'sprite_sheet' && (
        <button
          disabled={!hasOutput || isBusy}
          className="flex-1 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed text-gray-200 text-xs font-medium rounded-md transition-colors flex items-center justify-center gap-1.5"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Sheet
        </button>
      )}
      <button
        disabled={!hasOutput || isBusy}
        className="flex-1 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-medium rounded-md transition-colors flex items-center justify-center gap-1.5"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
        Review
      </button>
    </div>
  );
}

/* ─── Resource Type Switcher ─── */
function ResourceTypeSwitcher({
  pipelineType,
  onChange,
  disabled,
}: {
  pipelineType: PipelineType;
  onChange: (type: PipelineType) => void;
  disabled: boolean;
}) {
  return (
    <div className="flex items-center gap-1 p-1 bg-gray-800 rounded-lg">
      <button
        onClick={() => !disabled && onChange('3d_scene')}
        disabled={disabled}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
          pipelineType === '3d_scene'
            ? 'bg-blue-600 text-white'
            : disabled
            ? 'text-gray-600 cursor-not-allowed'
            : 'text-gray-400 hover:text-gray-200'
        }`}
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 7.5l-9-5.25L3 7.5m9 0l9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
        </svg>
        场景
      </button>
      <button
        onClick={() => !disabled && onChange('3d_character')}
        disabled={disabled}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
          pipelineType === '3d_character'
            ? 'bg-blue-600 text-white'
            : disabled
            ? 'text-gray-600 cursor-not-allowed'
            : 'text-gray-400 hover:text-gray-200'
        }`}
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
        角色
      </button>
      <button
        onClick={() => !disabled && onChange('2d_art')}
        disabled={disabled}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
          pipelineType === '2d_art'
            ? 'bg-blue-600 text-white'
            : disabled
            ? 'text-gray-600 cursor-not-allowed'
            : 'text-gray-400 hover:text-gray-200'
        }`}
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        2D
      </button>
    </div>
  );
}

/* ─── Main Page ─── */
export default function GeneratePage() {
  const [prompt, setPrompt] = useState('');
  const [negativePrompt, setNegativePrompt] = useState('');
  const [stylePreset, setStylePreset] = useState<StylePreset>('realistic');
  const [quality, setQuality] = useState<QualityLevel>('standard');
  const [pipelineType, setPipelineType] = useState<PipelineType>('3d_scene');

  const [usageType, setUsageType] = useState<UsageType>('icon');
  const [outputSize, setOutputSize] = useState<OutputSize>('512x512');
  const [removeBackground, setRemoveBackground] = useState(true);
  const [outputFormat, setOutputFormat] = useState<OutputFormat>('png');
  const [referenceFile, setReferenceFile] = useState<File | null>(null);

  const {
    currentRun,
    steps,
    error,
    isLoading: isPipelineLoading,
    startPipeline,
    resetPipeline,
    selectStage,
    selectedStageIndex,
    getCurrentModelUrl,
    getCurrentImageUrls,
    fetchPipelineStatus,
    pollStatus,
    deletePipeline,
    retryPipeline,
  } = usePipelineStore();

  const isGenerating = currentRun?.status === 'running' || currentRun?.status === 'pending';
  const isBusy = isPipelineLoading || isGenerating;
  const modelUrl = getCurrentModelUrl();
  const imageUrls = getCurrentImageUrls();

  const stages = pipelineType === '2d_art' ? PIPELINE_STAGES_2D : PIPELINE_STAGES_3D;
  const currentStep = selectedStageIndex ?? steps.filter((s) => s.status === 'completed').length - 1;

  const [elapsed, setElapsed] = useState(0);
  const startTimeRef = useRef<number | null>(null);
  useEffect(() => {
    if (isBusy && !startTimeRef.current) {
      startTimeRef.current = Date.now();
    }
    if (!isBusy) {
      startTimeRef.current = null;
      setElapsed(0);
    }
  }, [isBusy]);

  useEffect(() => {
    if (!isBusy || !startTimeRef.current) return;
    const id = setInterval(() => setElapsed(Date.now() - startTimeRef.current!), 200);
    return () => clearInterval(id);
  }, [isBusy]);

  const runningStage = steps.find((s) => s.status === 'running');
  const currentStageName = runningStage
    ? stages.find((s) => s.id === runningStage.stage)?.name
    : undefined;

  const bannerProgress = useMemo(() => {
    if (steps.length === 0) return 0;
    const done = steps.filter((s) => s.status === 'completed').length;
    const running = steps.filter((s) => s.status === 'running').length;
    return ((done + running * 0.5) / stages.length) * 100;
  }, [steps, stages.length]);

  const bannerStatus: 'idle' | 'loading' | 'running' | 'completed' | 'failed' = isPipelineLoading
    ? 'loading'
    : currentRun?.status === 'running' || currentRun?.status === 'pending'
    ? 'running'
    : currentRun?.status === 'completed'
    ? 'completed'
    : currentRun?.status === 'failed'
    ? 'failed'
    : 'idle';

  const handlePipelineTypeChange = useCallback(
    (newType: PipelineType) => {
      if (isBusy) return;
      if (newType !== pipelineType) {
        resetPipeline();
        setPipelineType(newType);
      }
    },
    [pipelineType, resetPipeline, isBusy],
  );

  const handleGenerate = useCallback(async () => {
    if (prompt.length < 10 || isBusy) return;
    try {
      if (pipelineType === '2d_art') {
        await startPipeline(prompt, negativePrompt, stylePreset, quality, '2d_art', {
          targetSize: outputSize,
          removeBackground,
          outputType: outputFormat,
          usageType,
        });
      } else {
        await startPipeline(prompt, negativePrompt, stylePreset, quality, pipelineType);
      }
    } catch (err) {
      console.error('Failed to start pipeline:', err);
    }
  }, [prompt, negativePrompt, stylePreset, quality, pipelineType, outputSize, removeBackground, outputFormat, usageType, startPipeline, isBusy]);

  const handleSelectStage = useCallback(
    (index: number | null) => {
      selectStage(index);
    },
    [selectStage],
  );

  useEffect(() => {
    if (currentRun?.id) {
      sessionStorage.setItem('pipelineId', currentRun.id);
    }
  }, [currentRun?.id]);

  useEffect(() => {
    const savedId = sessionStorage.getItem('pipelineId');
    if (savedId) {
      fetchPipelineStatus(savedId);
      const interval = setInterval(() => {
        pollStatus(savedId);
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [fetchPipelineStatus, pollStatus]);

  useEffect(() => {
    if (currentRun && ['completed', 'failed', 'partial'].includes(currentRun.status)) {
      sessionStorage.removeItem('pipelineId');
    }
  }, [currentRun?.status]);

  useEffect(() => {
    return () => {
      resetPipeline();
    };
  }, [resetPipeline]);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex-none px-6 py-3 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gray-100">Generate</h1>
            <p className="text-xs text-gray-500 mt-0.5">
              {pipelineType === '2d_art'
                ? 'Create 2D art from text prompts'
                : 'Create 3D assets from text prompts'}
            </p>
          </div>
          <ResourceTypeSwitcher
            pipelineType={pipelineType}
            onChange={handlePipelineTypeChange}
            disabled={isBusy}
          />
        </div>
      </div>

      {/* Status Banner */}
      <StatusBanner
        status={bannerStatus}
        currentStageName={currentStageName}
        progress={bannerProgress}
        elapsed={elapsed}
      />

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Left: Config */}
        <div className="w-72 p-3 overflow-y-auto border-r border-gray-800 flex-none">
          {pipelineType !== '2d_art' ? (
            <ConfigPanel3D
              prompt={prompt}
              onPromptChange={setPrompt}
              negativePrompt={negativePrompt}
              onNegativePromptChange={setNegativePrompt}
              stylePreset={stylePreset}
              onStylePresetChange={setStylePreset}
              quality={quality}
              onQualityChange={setQuality}
              onGenerate={handleGenerate}
              isBusy={isBusy}
              referenceFile={referenceFile}
              onReferenceFileChange={setReferenceFile}
            />
          ) : (
            <ConfigPanel2D
              prompt={prompt}
              onPromptChange={setPrompt}
              negativePrompt={negativePrompt}
              onNegativePromptChange={setNegativePrompt}
              stylePreset={stylePreset}
              onStylePresetChange={setStylePreset}
              usageType={usageType}
              onUsageTypeChange={setUsageType}
              outputSize={outputSize}
              onOutputSizeChange={setOutputSize}
              removeBackground={removeBackground}
              onRemoveBackgroundChange={setRemoveBackground}
              outputFormat={outputFormat}
              onOutputFormatChange={setOutputFormat}
              onGenerate={handleGenerate}
              isBusy={isBusy}
            />
          )}
        </div>

        {/* Center: Preview + Actions */}
        <div className="flex-1 p-3 flex flex-col gap-3 min-w-0">
          <div className="flex-1 min-h-0">
            {pipelineType !== '2d_art' ? (
              <PreviewPanel3D modelUrl={modelUrl} currentStep={currentStep} />
            ) : (
              <PreviewPanel2D imageUrls={imageUrls} currentStep={currentStep} />
            )}
          </div>
          {pipelineType !== '2d_art' ? (
            <ActionBar3D modelUrl={modelUrl} isBusy={isBusy} />
          ) : (
            <ActionBar2D imageUrls={imageUrls} outputFormat={outputFormat} isBusy={isBusy} />
          )}
        </div>

        {/* Right: Timeline */}
        <div className="w-72 p-3 overflow-y-auto border-l border-gray-800 flex-none">
          <PipelineTimeline
            steps={steps}
            selectedIndex={selectedStageIndex}
            onSelectStage={handleSelectStage}
            pipelineType={pipelineType}
            isRunning={isBusy}
            onRetry={() => currentRun?.id && retryPipeline(currentRun.id)}
            onDiscard={() => currentRun?.id && deletePipeline(currentRun.id)}
          />
        </div>
      </div>

      {/* Error Toast */}
      {error && (
        <div className="fixed bottom-4 right-4 bg-red-900/90 border border-red-700 text-red-200 px-4 py-3 rounded-lg shadow-lg max-w-sm">
          <p className="text-sm font-medium">Error</p>
          <p className="text-xs mt-0.5">{error}</p>
        </div>
      )}
    </div>
  );
}
