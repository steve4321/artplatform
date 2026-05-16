export type AssetType = 'model_3d' | 'texture_2d' | 'animation' | 'material';
export type Source = 'generated' | 'uploaded' | 'imported';
export type State = 'draft' | 'processing' | 'review' | 'approved' | 'published' | 'deprecated' | 'rejected';
export type PipelineStatus = 'pending' | 'running' | 'completed' | 'failed';
export type StepStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface Asset {
  id: string;
  name: string;
  assetType: AssetType;
  source: Source;
  state: State;
  createdAt: string;
  updatedAt: string;
  fileUrl: string | null;
  thumbnailUrl: string | null;
  metadata: Record<string, unknown>;
}

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

export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  createdAt: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export type StylePreset = 'realistic' | 'anime' | 'cartoon' | 'fantasy' | 'sci-fi';
export type QualityLevel = 'draft' | 'standard' | 'high';

export interface GenerationConfig {
  prompt: string;
  negativePrompt?: string;
  stylePreset: StylePreset;
  quality: QualityLevel;
  referenceImageUrl?: string | null;
}

export interface StageInfo {
  id: string;
  name: string;
  icon: string;
  status: StepStatus;
  duration?: number;
  error?: string | null;
  outputUrl?: string | null;
}

export const PIPELINE_STAGES: StageInfo[] = [
  { id: 'text_to_image', name: 'Text→Image', icon: '🖼', status: 'pending' },
  { id: '3d_generate', name: '3D Generate', icon: '📦', status: 'pending' },
  { id: 'cleanup', name: 'Cleanup', icon: '🧹', status: 'pending' },
  { id: 'uv_material', name: 'UV+Material', icon: '🎨', status: 'pending' },
  { id: 'rig', name: 'Rig', icon: '🦴', status: 'pending' },
  { id: 'animate', name: 'Animate', icon: '🎬', status: 'pending' },
];