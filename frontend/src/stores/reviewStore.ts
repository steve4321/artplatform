import { create } from 'zustand';
import client from '../api/client';
import type { Review } from '../types';

interface ReviewState {
  reviews: Review[];
  isLoading: boolean;
  error: string | null;
  fetchAssetReviews: (assetId: string, page?: number, pageSize?: number) => Promise<void>;
  submitReview: (payload: { assetId: string; version: number; decision: string; notes?: string }) => Promise<void>;
  reset: () => void;
}

export const useReviewStore = create<ReviewState>((set) => ({
  reviews: [],
  isLoading: false,
  error: null,

  fetchAssetReviews: async (assetId: string, page = 1, pageSize = 20) => {
    set({ isLoading: true, error: null });
    try {
      const response = await client.get(
        `/api/v1/assets/${assetId}/reviews?page=${page}&page_size=${pageSize}`
      );
      set({
        reviews: response.data.items || [],
        isLoading: false,
      });
    } catch {
      set({ isLoading: false, error: 'Failed to fetch reviews' });
    }
  },

  submitReview: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      await client.post('/api/v1/reviews', {
        asset_id: payload.assetId,
        version: payload.version,
        decision: payload.decision,
        notes: payload.notes || null,
      });
      set({ isLoading: false });
    } catch {
      set({ isLoading: false, error: 'Failed to submit review' });
      throw new Error('Failed to submit review');
    }
  },

  reset: () => {
    set({ reviews: [], isLoading: false, error: null });
  },
}));