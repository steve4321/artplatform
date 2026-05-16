export type AssetType = 'model' | 'texture' | 'animation' | 'material';
export type Source = 'generated' | 'uploaded' | 'imported';
export type State = 'draft' | 'pending_review' | 'approved' | 'rejected';
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