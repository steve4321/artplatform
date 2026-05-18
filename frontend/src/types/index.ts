export interface User {
  id: string;
  teamId: string | null;
  email: string;
  displayName: string;
  role: string;
  isActive: boolean;
  createdAt: string | null;
}

export interface UserBrief {
  id: string;
  displayName: string;
  email: string;
}

export interface AssetVersion {
  id: string;
  assetId: string;
  version: number;
  storageKey: string;
  storageKeyThumbnail: string | null;
  fileFormat: string;
  fileSizeBytes: number | null;
  checksumSha256: string | null;
  sourceType: string;
  pipelineRunId: string | null;
  createdAt: string;
}

export interface AssetDependency {
  dependentAssetId: string;
  dependencyAssetId: string;
  dependencyType: string;
}

export interface Asset {
  id: string;
  teamId: string;
  name: string;
  description: string;
  assetType: string;
  source: string;
  state: string;
  currentVersion: number;
  parentAssetId: string | null;
  metadata: Record<string, unknown>;
  tags: string[];
  createdBy: string | null;
  createdAt: string;
  updatedAt: string;
  versions: AssetVersion[];
  dependencies: AssetDependency[];
  createdByUser: UserBrief | null;
}

export interface PipelineStep {
  id: string;
  pipelineRunId: string;
  stageOrder: number;
  stage: string;
  processorName: string;
  status: string;
  inputArtifactIds: string[];
  outputArtifactIds: string[];
  config: Record<string, unknown>;
  durationMs: number | null;
  errorMessage: string | null;
  startedAt: string | null;
  completedAt: string | null;
}

export interface PipelineRun {
  id: string;
  assetId: string;
  prompt: string;
  referenceImageKey: string | null;
  status: string;
  config: Record<string, unknown>;
  totalStages: number | null;
  completedStages: number;
  createdAt: string;
  completedAt: string | null;
  steps: PipelineStep[];
}

export interface Review {
  id: string;
  assetId: string;
  version: number;
  reviewerId: string;
  decision: string;
  notes: string | null;
  reviewedAt: string;
  reviewer: UserBrief | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

export function getLatestVersionDownloadUrl(assetId: string, version: number): string {
  return `/api/v1/assets/${assetId}/versions/${version}/download`;
}

export type AssetType = 'model_3d' | 'texture_2d' | 'animation' | 'material' | 'sprite';
export type Source = 'ai_generated' | 'manual_upload' | 'hybrid';
export type State = 'draft' | 'processing' | 'review' | 'approved' | 'rejected' | 'published' | 'deprecated';
export type PipelineStatus = 'pending' | 'running' | 'completed' | 'partial' | 'failed';
export type StepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

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
  status: string;
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