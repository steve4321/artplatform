import { useEffect, useState, useCallback, Suspense, lazy } from 'react';
import client from '../api/client';
import type { Asset } from '../types';

const AssetViewer = lazy(() => import('../components/viewer/AssetViewer'));

interface TextureInfo {
  storageKey: string;
  textureType: string;
  url: string;
}

function useAssetTextures() {
  const [cache, setCache] = useState<Record<string, TextureInfo[]>>({});

  const fetchTextures = useCallback(async (assetId: string) => {
    if (cache[assetId]) return cache[assetId];
    try {
      const resp = await client.get(`/api/v1/assets/${assetId}/textures`);
      const textures: TextureInfo[] = resp.data || [];
      setCache((prev) => ({ ...prev, [assetId]: textures }));
      return textures;
    } catch {
      return [];
    }
  }, [cache]);

  return { texturesCache: cache, fetchTextures };
}

function ReviewsPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [previewAsset, setPreviewAsset] = useState<Asset | null>(null);
  const [downloadingFbx, setDownloadingFbx] = useState<string | null>(null);
  const { texturesCache, fetchTextures } = useAssetTextures();

  const fetchReviewQueue = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await client.get('/api/v1/assets?state=review&page=1&page_size=50');
      const items = response.data.items || [];
      setAssets(items);
      items.forEach((a: Asset) => { fetchTextures(a.id); });
    } catch {
      console.error('Failed to fetch review queue');
    } finally {
      setIsLoading(false);
    }
  }, [fetchTextures]);

  useEffect(() => {
    fetchReviewQueue();
  }, [fetchReviewQueue]);

  const handleReview = async (assetId: string, decision: string) => {
    const labels: Record<string, string> = {
      approved: 'approve',
      rejected: 'reject',
      changes_requested: 'request changes for',
    };
    if (!window.confirm(`Are you sure you want to ${labels[decision]} this asset?`)) return;
    setSubmitting(assetId);
    try {
      if (decision === 'approved') {
        await client.patch(`/api/v1/assets/${assetId}/state`, { state: 'approved' });
      } else if (decision === 'rejected') {
        await client.patch(`/api/v1/assets/${assetId}/state`, { state: 'rejected' });
      } else if (decision === 'changes_requested') {
        await client.patch(`/api/v1/assets/${assetId}/state`, { state: 'draft' });
      }
      setAssets((prev) => prev.filter((a) => a.id !== assetId));
    } catch (err) {
      console.error('Failed to submit review:', err);
    } finally {
      setSubmitting(null);
    }
  };

  const handleDownloadGlb = (asset: Asset) => {
    const latest = asset.versions?.[asset.versions.length - 1];
    if (latest?.storageKey) {
      window.open(`/local-storage/${latest.storageKey}`, '_blank');
    }
  };

  const handleDownloadFbx = async (asset: Asset) => {
    const latest = asset.versions?.[asset.versions.length - 1];
    if (!latest) return;
    setDownloadingFbx(asset.id);
    try {
      const resp = await client.get(
        `/api/v1/assets/${asset.id}/export/fbx?version=${latest.version}`
      );
      if (resp.data?.url) {
        window.open(resp.data.url, '_blank');
      }
    } catch (err) {
      console.error('FBX export failed:', err);
    } finally {
      setDownloadingFbx(null);
    }
  };

  const getAlbedoUrl = (assetId: string): string | null => {
    const textures = texturesCache[assetId];
    if (!textures) return null;
    const albedo = textures.find((t) => t.textureType === 'albedo');
    return albedo?.storageKey ? `/local-storage/${albedo.storageKey}` : null;
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
                <div
                  className="w-40 h-40 bg-gray-800 rounded-lg flex items-center justify-center flex-shrink-0 overflow-hidden cursor-pointer hover:ring-2 hover:ring-blue-500 transition-all"
                  onClick={() => setPreviewAsset(asset)}
                >
                  {asset.assetType === 'model_3d' ? (
                    <div className="w-full h-full flex flex-col items-center justify-center gap-2">
                      <svg className="w-10 h-10 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
                      </svg>
                      <span className="text-blue-400 text-xs font-medium">3D Model</span>
                    </div>
                  ) : asset.versions && asset.versions.length > 0 ? (
                    (() => {
                      const latest = asset.versions[asset.versions.length - 1];
                      const key = latest.storageKeyThumbnail ?? latest.storageKey;
                      const url = key ? `/local-storage/${key}` : null;
                      return url ? (
                        <img src={url} alt={asset.name} className="w-full h-full object-cover pointer-events-none" />
                      ) : (
                        <span className="text-gray-600 text-xs">No preview</span>
                      );
                    })()
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
                  {getAlbedoUrl(asset.id) && (
                    <div className="mt-3">
                      <img
                        src={getAlbedoUrl(asset.id)!}
                        alt="Albedo preview"
                        className="w-20 h-20 rounded-md object-cover border border-gray-700"
                      />
                    </div>
                  )}
                  <div className="flex flex-wrap gap-3 mt-4">
                    <button
                      onClick={() => handleReview(asset.id, 'approved')}
                      disabled={submitting === asset.id}
                      className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      {submitting === asset.id ? 'Submitting...' : 'Approve'}
                    </button>
                    <button
                      onClick={() => handleReview(asset.id, 'rejected')}
                      disabled={submitting === asset.id}
                      className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => handleReview(asset.id, 'changes_requested')}
                      disabled={submitting === asset.id}
                      className="px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-300 text-sm font-medium rounded-lg border border-gray-700 transition-colors"
                    >
                      Request Changes
                    </button>
                    <div className="flex gap-2 ml-auto items-center">
                      <button
                        onClick={() => handleDownloadGlb(asset)}
                        disabled={!asset.versions?.length}
                        className="px-3 py-2 bg-cyan-700/60 hover:bg-cyan-600/60 disabled:opacity-40 text-cyan-100 text-xs font-medium rounded-lg border border-cyan-600/40 transition-colors flex items-center gap-1.5"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        下载 GLB
                      </button>
                      <button
                        onClick={() => handleDownloadFbx(asset)}
                        disabled={!asset.versions?.length || downloadingFbx === asset.id}
                        className="px-3 py-2 bg-amber-700/60 hover:bg-amber-600/60 disabled:opacity-40 text-amber-100 text-xs font-medium rounded-lg border border-amber-600/40 transition-colors flex items-center gap-1.5"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        {downloadingFbx === asset.id ? '导出中...' : '导出 FBX'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {previewAsset && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={() => setPreviewAsset(null)} />
          <div className="relative max-w-4xl max-h-[90vh] w-full mx-4">
            <button
              onClick={() => setPreviewAsset(null)}
              className="absolute -top-10 right-2 text-white hover:text-gray-300 text-sm"
            >
              Close
            </button>
            {(() => {
              if (previewAsset.assetType === 'model_3d') {
                const latest = previewAsset.versions?.[previewAsset.versions.length - 1];
                const modelUrl = latest?.storageKey ? `/local-storage/${latest.storageKey}` : null;
                if (!modelUrl) return <div className="text-white">No 3D model available</div>;
                return (
                  <div className="w-full" style={{ height: '70vh' }}>
                    <Suspense fallback={
                      <div className="w-full h-full flex items-center justify-center">
                        <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                      </div>
                    }>
                      <AssetViewer modelUrl={modelUrl} className="w-full h-full" />
                    </Suspense>
                  </div>
                );
              }
              const latest = previewAsset.versions?.[previewAsset.versions.length - 1];
              const key = latest?.storageKeyThumbnail ?? latest?.storageKey;
              const url = key ? `/local-storage/${key}` : null;
              if (!url) return <div className="text-white">No preview available</div>;
              return (
                <img
                  src={url}
                  alt={previewAsset.name}
                  className="w-full h-auto max-h-[85vh] object-contain rounded-lg"
                />
              );
            })()}
            <div className="text-center mt-4">
              <p className="text-gray-300 text-sm">{previewAsset.name}</p>
              <p className="text-gray-500 text-xs mt-1">{previewAsset.description}</p>
              <div className="flex justify-center gap-3 mt-3">
                <button
                  onClick={() => handleDownloadGlb(previewAsset)}
                  disabled={!previewAsset.versions?.length}
                  className="px-4 py-2 bg-cyan-700/60 hover:bg-cyan-600/60 disabled:opacity-40 text-cyan-100 text-sm font-medium rounded-lg border border-cyan-600/40 transition-colors flex items-center gap-1.5"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  下载 GLB
                </button>
                <button
                  onClick={() => handleDownloadFbx(previewAsset)}
                  disabled={!previewAsset.versions?.length || downloadingFbx === previewAsset.id}
                  className="px-4 py-2 bg-amber-700/60 hover:bg-amber-600/60 disabled:opacity-40 text-amber-100 text-sm font-medium rounded-lg border border-amber-600/40 transition-colors flex items-center gap-1.5"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  {downloadingFbx === previewAsset.id ? '导出中...' : '导出 FBX'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ReviewsPage;