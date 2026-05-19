import { create } from 'zustand';
import client from '../api/client';
import type { Asset, AssetVersion } from '../types';

export type { Asset, AssetVersion };

export type AssetType = 'model_3d' | 'texture_2d' | 'animation' | 'material' | 'sprite';
export type Source = 'ai_generated' | 'manual_upload' | 'hybrid';
export type State = 'draft' | 'processing' | 'review' | 'approved' | 'rejected' | 'published' | 'deprecated';

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
  createAsset: (payload: { name: string; description?: string; assetType: AssetType; tags?: string[] }) => Promise<Asset>;
  uploadVersion: (assetId: string, file: File) => Promise<AssetVersion>;
  getDownloadUrl: (assetId: string, version: number) => string;
  submitForReview: (assetId: string) => Promise<void>;
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
      if (filters.state !== 'all') {
        params.append('state', filters.state);
        params.append('include_all', 'true');
      }
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

  createAsset: async (payload) => {
    const response = await client.post('/api/v1/assets', {
      name: payload.name,
      description: payload.description || '',
      asset_type: payload.assetType,
      tags: payload.tags || [],
    });
    await get().fetchAssets();
    return response.data;
  },

  uploadVersion: async (assetId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await client.post(`/api/v1/assets/${assetId}/versions`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getDownloadUrl: (assetId: string, version: number) => {
    return `/api/v1/assets/${assetId}/versions/${version}/download`;
  },

  submitForReview: async (assetId: string) => {
    await client.patch(`/api/v1/assets/${assetId}/state`, { state: 'review' });
    await get().fetchAssets();
  },

  deleteAsset: async (assetId: string) => {
    await client.delete(`/api/v1/assets/${assetId}`);
    await get().fetchAssets();
  },
}));