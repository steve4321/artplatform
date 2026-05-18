import { create } from 'zustand';
import client from '../api/client';
import type { Asset } from '../types';

interface DashboardStats {
  totalAssets: number;
  pendingReviews: number;
  activePipelines: number;
}

interface DashboardState {
  stats: DashboardStats;
  recentAssets: Asset[];
  isLoading: boolean;
  error: string | null;
  fetchDashboard: () => Promise<void>;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  stats: {
    totalAssets: 0,
    pendingReviews: 0,
    activePipelines: 0,
  },
  recentAssets: [],
  isLoading: false,
  error: null,

  fetchDashboard: async () => {
    set({ isLoading: true, error: null });
    try {
      const [assetsRes, reviewRes, pipelinesRes, recentRes] = await Promise.all([
        client.get('/api/v1/assets?page=1&page_size=1'),
        client.get('/api/v1/assets?state=review&page=1&page_size=1'),
        client.get('/api/v1/pipelines?status=running&page=1&page_size=1'),
        client.get('/api/v1/assets?page=1&page_size=5'),
      ]);

      set({
        stats: {
          totalAssets: assetsRes.data.total || 0,
          pendingReviews: reviewRes.data.total || 0,
          activePipelines: pipelinesRes.data.total || 0,
        },
        recentAssets: recentRes.data.items || [],
        isLoading: false,
      });
    } catch {
      set({ isLoading: false, error: 'Failed to fetch dashboard data' });
    }
  },
}));