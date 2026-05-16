import { create } from 'zustand';

export type AssetType = 'model' | 'texture' | 'animation' | 'material';
export type Source = 'generated' | 'uploaded' | 'imported';
export type State = 'draft' | 'pending_review' | 'approved' | 'rejected';

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

interface AssetState {
  assets: Asset[];
  isLoading: boolean;
  error: string | null;
  fetchAssets: () => Promise<void>;
  getAssetById: (id: string) => Asset | undefined;
}

export const useAssetStore = create<AssetState>((set, get) => ({
  assets: [],
  isLoading: false,
  error: null,
  fetchAssets: async () => {
    set({ isLoading: true, error: null });
    try {
      await new Promise((resolve) => setTimeout(resolve, 500));
      set({ isLoading: false });
    } catch {
      set({ isLoading: false, error: 'Failed to fetch assets' });
    }
  },
  getAssetById: (id: string) => get().assets.find((asset) => asset.id === id),
}));