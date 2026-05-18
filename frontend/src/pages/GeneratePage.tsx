import { useState, useCallback, useEffect, useMemo } from 'react';
import { AssetViewer } from '../components/viewer';
import { usePipelineStore, PipelineStep } from '../stores/pipelineStore';

type StylePreset = 'realistic' | 'anime' | 'cartoon' | 'fantasy' | 'sci-fi';
type QualityLevel = 'draft' | 'standard' | 'high';

interface StageConfig {
  id: string;
  name: string;
  icon: string;
}

const PIPELINE_STAGES: StageConfig[] = [
  { id: 'text_to_image', name: 'Text→Image', icon: '🖼' },
  { id: '3d_generate', name: '3D Generate', icon: '📦' },
  { id: 'cleanup', name: 'Cleanup', icon: '🧹' },
  { id: 'uv_material', name: 'UV+Material', icon: '🎨' },
  { id: 'rig', name: 'Rig', icon: '🦴' },
  { id: 'animate', name: 'Animate', icon: '🎬' },
];

const STYLE_PRESETS: { value: StylePreset; label: string }[] = [
  { value: 'realistic', label: 'Realistic' },
  { value: 'anime', label: 'Anime' },
  { value: 'cartoon', label: 'Cartoon' },
  { value: 'fantasy', label: 'Fantasy' },
  { value: 'sci-fi', label: 'Sci-Fi' },
];

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
    <div className={`text-xl ${statusStyles[status] || 'text-gray-600'}`}>
      {status === 'pending' ? stage.icon : statusSymbols[status] || stage.icon}
    </div>
  );
}

function PipelineTimeline({
  steps,
  selectedIndex,
  onSelectStage,
}: {
  steps: PipelineStep[];
  selectedIndex: number | null;
  onSelectStage: (index: number | null) => void;
}) {
  const overallProgress = useMemo(() => {
    if (steps.length === 0) return 0;
    const completed = steps.filter((s) => s.status === 'completed' || s.status === 'failed').length;
    return (completed / steps.length) * 100;
  }, [steps]);

  const hasRunning = steps.some((s) => s.status === 'running');

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 h-full flex flex-col">
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Pipeline Timeline</h3>

      <div className="mb-4">
        <div className="flex items-center justify-between text-xs text-gray-500 mb-2">
          <span>Progress</span>
          <span>{Math.round(overallProgress)}%</span>
        </div>
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ${
              hasRunning ? 'bg-blue-600 animate-pulse' : 'bg-green-600'
            }`}
            style={{ width: `${overallProgress}%` }}
          />
        </div>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto">
        {PIPELINE_STAGES.map((stage, index) => {
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
              className={`w-full flex items-center gap-3 p-3 rounded-lg transition-all text-left ${
                isSelected
                  ? 'bg-blue-900/30 border border-blue-700'
                  : isClickable
                  ? 'bg-gray-800/50 border border-gray-700 hover:border-gray-600 hover:bg-gray-800'
                  : 'bg-gray-900 border border-gray-800'
              }`}
            >
              <StageIcon stage={stage} status={status} />
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium ${status === 'pending' ? 'text-gray-500' : 'text-gray-200'}`}>
                  {stage.name}
                </p>
                {duration && (
                  <p className="text-xs text-gray-500">{Math.round(duration / 1000)}s</p>
                )}
                {error && status === 'failed' && (
                  <p className="text-xs text-red-400 truncate">{error}</p>
                )}
              </div>
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${
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
        <button className="mt-4 w-full py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors">
          Retry Failed Stage
        </button>
      )}
    </div>
  );
}

function ConfigPanel({
  prompt,
  onPromptChange,
  negativePrompt,
  onNegativePromptChange,
  stylePreset,
  onStylePresetChange,
  quality,
  onQualityChange,
  onGenerate,
  isGenerating,
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
  isGenerating: boolean;
}) {
  const [showNegative, setShowNegative] = useState(false);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          Prompt <span className="text-red-500">*</span>
        </label>
        <textarea
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          placeholder="A medieval warrior character with sword and shield, game-ready topology, PBR textures..."
          className="w-full h-32 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-600 resize-none"
        />
        <p className="mt-1 text-xs text-gray-500">{prompt.length} characters (min 10)</p>
      </div>

      <div>
        <button
          type="button"
          onClick={() => setShowNegative(!showNegative)}
          className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-300 transition-colors"
        >
          <svg
            className={`w-4 h-4 transition-transform ${showNegative ? 'rotate-90' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          Negative Prompt (optional)
        </button>
        {showNegative && (
          <textarea
            value={negativePrompt}
            onChange={(e) => onNegativePromptChange(e.target.value)}
            placeholder="Blurry, low quality, distorted anatomy..."
            className="mt-2 w-full h-20 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-600 resize-none"
          />
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">Style Preset</label>
        <select
          value={stylePreset}
          onChange={(e) => onStylePresetChange(e.target.value as StylePreset)}
          className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:border-blue-600"
        >
          {STYLE_PRESETS.map((preset) => (
            <option key={preset.value} value={preset.value}>
              {preset.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">Quality</label>
        <div className="flex gap-2">
          {(['draft', 'standard', 'high'] as QualityLevel[]).map((q) => (
            <button
              key={q}
              onClick={() => onQualityChange(q)}
              className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                quality === q
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200'
              }`}
            >
              {q.charAt(0).toUpperCase() + q.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">Reference Image (optional)</label>
        <button className="w-full py-3 border-2 border-dashed border-gray-700 rounded-lg text-gray-500 hover:border-gray-600 hover:text-gray-400 transition-colors flex items-center justify-center gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
            />
          </svg>
          Upload Image
        </button>
      </div>

      <button
        onClick={onGenerate}
        disabled={prompt.length < 10 || isGenerating}
        className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
      >
        {isGenerating ? (
          <>
            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Generating...
          </>
        ) : (
          <>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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

function PreviewPanel({
  modelUrl,
  currentStep,
}: {
  modelUrl: string | null;
  currentStep: number;
}) {
  const stepNames = PIPELINE_STAGES.map((s) => s.name);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-300">3D Preview</h3>
        {currentStep >= 0 && (
          <span className="text-xs text-gray-500">
            Showing: {stepNames[currentStep] || 'Final Result'}
          </span>
        )}
      </div>
      <div className="flex-1 relative">
        {modelUrl ? (
          <AssetViewer modelUrl={modelUrl} className="w-full h-full" autoPlay />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-600">
            <svg className="w-20 h-20 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
              />
            </svg>
            <p className="text-gray-500 font-medium">No model loaded</p>
            <p className="text-gray-600 text-sm mt-1">Enter a prompt and click Generate</p>
          </div>
        )}
      </div>
    </div>
  );
}

function ActionBar({
  modelUrl,
  isGenerating,
}: {
  modelUrl: string | null;
  isGenerating: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <button
        disabled={!modelUrl || isGenerating}
        className="flex-1 py-3 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed text-gray-200 font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
          />
        </svg>
        Download FBX
      </button>
      <button
        disabled={!modelUrl || isGenerating}
        className="flex-1 py-3 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed text-gray-200 font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
          />
        </svg>
        Download GLB
      </button>
      <button
        disabled={!modelUrl || isGenerating}
        className="flex-1 py-3 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
          />
        </svg>
        Submit for Review
      </button>
    </div>
  );
}

export default function GeneratePage() {
  const [prompt, setPrompt] = useState('');
  const [negativePrompt, setNegativePrompt] = useState('');
  const [stylePreset, setStylePreset] = useState<StylePreset>('realistic');
  const [quality, setQuality] = useState<QualityLevel>('standard');

  const { currentRun, steps, error, startPipeline, resetPipeline, selectStage, selectedStageIndex, getCurrentModelUrl } =
    usePipelineStore();

  const isGenerating = currentRun?.status === 'running';
  const modelUrl = getCurrentModelUrl();

  const handleGenerate = useCallback(async () => {
    if (prompt.length < 10) return;
    try {
      await startPipeline(prompt, negativePrompt, stylePreset, quality);
    } catch (err) {
      console.error('Failed to start pipeline:', err);
    }
  }, [prompt, negativePrompt, stylePreset, quality, startPipeline]);

  const handleSelectStage = useCallback(
    (index: number | null) => {
      selectStage(index);
    },
    [selectStage]
  );

  useEffect(() => {
    return () => {
      resetPipeline();
    };
  }, [resetPipeline]);

  return (
    <div className="h-full flex flex-col">
      <div className="flex-0 px-6 py-4 border-b border-gray-800">
        <h1 className="text-2xl font-bold text-gray-100">Generation Workflow</h1>
        <p className="text-gray-400 mt-1">Create 3D assets from text prompts</p>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className="w-72 p-4 overflow-y-auto border-r border-gray-800">
          <ConfigPanel
            prompt={prompt}
            onPromptChange={setPrompt}
            negativePrompt={negativePrompt}
            onNegativePromptChange={setNegativePrompt}
            stylePreset={stylePreset}
            onStylePresetChange={setStylePreset}
            quality={quality}
            onQualityChange={setQuality}
            onGenerate={handleGenerate}
            isGenerating={isGenerating}
          />
        </div>

        <div className="flex-1 p-4 flex flex-col gap-4 min-w-0">
          <div className="flex-1 min-h-0">
            <PreviewPanel modelUrl={modelUrl} currentStep={selectedStageIndex ?? steps.filter((s) => s.status === 'completed').length - 1} />
          </div>
          <ActionBar modelUrl={modelUrl} isGenerating={isGenerating} />
        </div>

        <div className="w-80 p-4 overflow-y-auto border-l border-gray-800">
          <PipelineTimeline
            steps={steps}
            selectedIndex={selectedStageIndex}
            onSelectStage={handleSelectStage}
          />
        </div>
      </div>

      {error && (
        <div className="fixed bottom-4 right-4 bg-red-900/90 border border-red-700 text-red-200 px-4 py-3 rounded-lg shadow-lg">
          <p className="font-medium">Error</p>
          <p className="text-sm">{error}</p>
        </div>
      )}
    </div>
  );
}