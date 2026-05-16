import { create } from 'zustand';
import client from '../api/client';

export type AssetType = 'model_3d' | 'texture_2d' | 'animation' | 'material';
export type Source = 'generated' | 'uploaded' | 'imported';
export type State = 'draft' | 'processing' | 'review' | 'approved' | 'published' | 'deprecated' | 'rejected';

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

export interface AssetFilters {
  search: string;
  assetType: AssetType | 'all';
  state: State | 'all';
}

interface AssetState {
  assets: Asset[];
  isLoading: boolean;
  error: string | null;
  filters: AssetFilters;
  page: number;
  pageSize: number;
  total: number;
  fetchAssets: () => Promise<void>;
  getAssetById: (id: string) => Asset | undefined;
  setFilters: (filters: Partial<AssetFilters>) => void;
  setPage: (page: number) => void;
  resetFilters: () => void;
}

export const useAssetStore = create<AssetState>((set, get) => ({
  assets: [],
  isLoading: false,
  error: null,
  filters: {
    search: '',
    assetType: 'all',
    state: 'all',
  },
  page: 1,
  pageSize: 20,
  total: 0,

  fetchAssets: async () => {
    set({ isLoading: true, error: null });
    try {
      const { filters, page, pageSize } = get();
      const params = new URLSearchParams();

      if (filters.search) params.append('search', filters.search);
      if (filters.assetType !== 'all') params.append('asset_type', filters.assetType);
      if (filters.state !== 'all') params.append('state', filters.state);
      params.append('page', page.toString());
      params.append('page_size', pageSize.toString());

      const response = await client.get(`/api/v1/assets?${params.toString()}`);
      set({
        assets: response.data.items || [],
        total: response.data.total || 0,
        isLoading: false,
      });
    } catch {
      set({ isLoading: false, error: 'Failed to fetch assets' });
    }
  },

  getAssetById: (id: string) => get().assets.find((asset) => asset.id === id),

  setFilters: (newFilters: Partial<AssetFilters>) => {
    set((state) => ({
      filters: { ...state.filters, ...newFilters },
      page: 1,
    }));
    get().fetchAssets();
  },

  setPage: (page: number) => {
    set({ page });
    get().fetchAssets();
  },

  resetFilters: () => {
    set({
      filters: { search: '', assetType: 'all', state: 'all' },
      page: 1,
    });
    get().fetchAssets();
  },
}));