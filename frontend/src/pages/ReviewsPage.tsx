import { useEffect, useState, useCallback } from 'react';
import client from '../api/client';
import type { Asset } from '../types';

function ReviewsPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [submitting, setSubmitting] = useState<string | null>(null);

  const fetchReviewQueue = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await client.get('/api/v1/assets?state=review&page=1&page_size=50');
      setAssets(response.data.items || []);
    } catch {
      console.error('Failed to fetch review queue');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReviewQueue();
  }, [fetchReviewQueue]);

  const handleReview = async (assetId: string, version: number, decision: string) => {
    setSubmitting(assetId);
    try {
      if (decision === 'approved') {
        await client.patch(`/api/v1/assets/${assetId}/state`, { state: 'approved' });
      } else if (decision === 'rejected') {
        await client.delete(`/api/v1/assets/${assetId}`);
      }
      await fetchReviewQueue();
    } catch (err) {
      console.error('Failed to submit review:', err);
    } finally {
      setSubmitting(null);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Reviews</h1>
          <p className="text-gray-400 mt-1">Review queue for pending assets</p>
        </div>
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Reviews</h1>
        <p className="text-gray-400 mt-1">Review queue for pending assets</p>
      </div>
      {assets.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-12 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-800 flex items-center justify-center">
            <svg className="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-gray-400 text-lg">No assets pending review</p>
          <p className="text-gray-500 text-sm mt-1">All caught up!</p>
        </div>
      ) : (
        <div className="space-y-4">
          {assets.map((asset) => (
            <div key={asset.id} className="bg-gray-900 border border-gray-800 rounded-lg p-6">
              <div className="flex items-start gap-4">
                <div className="w-24 h-24 bg-gray-800 rounded-lg flex items-center justify-center flex-shrink-0">
                  {asset.versions && asset.versions.length > 0 ? (
                    <span className="text-gray-500 text-xs">v{asset.currentVersion}</span>
                  ) : (
                    <span className="text-gray-600 text-sm">Preview</span>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-100">{asset.name}</h3>
                  <p className="text-sm text-gray-400 mt-1">
                    {asset.createdByUser?.displayName || 'Unknown'} •{' '}
                    {new Date(asset.createdAt).toLocaleDateString()}
                  </p>
                  <p className="text-gray-300 mt-2 line-clamp-2">{asset.description || 'No description'}</p>
                  <div className="flex gap-3 mt-4">
                    <button
                      onClick={() => handleReview(asset.id, asset.currentVersion, 'approved')}
                      disabled={submitting === asset.id}
                      className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      {submitting === asset.id ? 'Submitting...' : 'Approve'}
                    </button>
                    <button
                      onClick={() => handleReview(asset.id, asset.currentVersion, 'rejected')}
                      disabled={submitting === asset.id}
                      className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => handleReview(asset.id, asset.currentVersion, 'changes_requested')}
                      disabled={submitting === asset.id}
                      className="px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-300 text-sm font-medium rounded-lg border border-gray-700 transition-colors"
                    >
                      Request Changes
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default ReviewsPage;