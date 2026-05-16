import { useState, useCallback, useEffect } from 'react';
import { useAssetStore, Asset } from '../stores/assetStore';
import { AssetGrid, AssetFilters } from '../components/assets';
import { AssetViewer } from '../components/viewer';

function AssetDetailModal({
  asset,
  onClose,
}: {
  asset: Asset;
  onClose: () => void;
}) {
  const [activeTab, setActiveTab] = useState<'preview' | 'details'>('preview');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />

      <div className="relative bg-gray-900 border border-gray-800 rounded-xl shadow-2xl w-full max-w-5xl mx-4 h-[85vh] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div className="flex items-center gap-4">
            <h2 className="text-xl font-semibold text-gray-100">{asset.name}</h2>
            <span
              className={`px-2 py-1 text-xs font-medium rounded-full ${
                asset.state === 'approved' || asset.state === 'published'
                  ? 'bg-green-900/50 text-green-400'
                  : asset.state === 'review'
                  ? 'bg-yellow-900/50 text-yellow-400'
                  : asset.state === 'processing'
                  ? 'bg-blue-900/50 text-blue-400'
                  : asset.state === 'rejected' || asset.state === 'deprecated'
                  ? 'bg-red-900/50 text-red-400'
                  : 'bg-gray-800 text-gray-400'
              }`}
            >
              {asset.state.replace('_', ' ')}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 transition-colors p-1"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <div className="flex border-b border-gray-800">
          <button
            onClick={() => setActiveTab('preview')}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'preview'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            Preview
          </button>
          <button
            onClick={() => setActiveTab('details')}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'details'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            Details
          </button>
        </div>

        <div className="flex-1 overflow-hidden">
          {activeTab === 'preview' ? (
            <div className="h-full p-4">
              {asset.fileUrl ? (
                <AssetViewer modelUrl={asset.fileUrl} className="w-full h-full" autoPlay />
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-gray-600">
                  <svg className="w-20 h-20 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1}
                      d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
                    />
                  </svg>
                  <p className="text-gray-500">No preview available</p>
                </div>
              )}
            </div>
          ) : (
            <div className="h-full overflow-y-auto p-6">
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Information</h4>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Type</span>
                      <span className="text-gray-200">{asset.assetType.replace('_', ' ')}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Source</span>
                      <span className="text-gray-200 capitalize">{asset.source}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Created</span>
                      <span className="text-gray-200">
                        {new Date(asset.createdAt).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                        })}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Updated</span>
                      <span className="text-gray-200">
                        {new Date(asset.updatedAt).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                        })}
                      </span>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Metadata</h4>
                  <div className="bg-gray-800 rounded-lg p-4">
                    {Object.keys(asset.metadata).length > 0 ? (
                      <pre className="text-xs text-gray-400 overflow-x-auto">
                        {JSON.stringify(asset.metadata, null, 2)}
                      </pre>
                    ) : (
                      <p className="text-gray-500 text-sm">No metadata available</p>
                    )}
                  </div>
                </div>
              </div>

              <div className="mt-8 flex gap-3">
                <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors">
                  Download
                </button>
                <button className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 font-medium rounded-lg transition-colors">
                  Edit
                </button>
                {asset.state === 'draft' && (
                  <button className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg transition-colors">
                    Submit for Review
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AssetsPage() {
  const {
    assets,
    isLoading,
    filters,
    page,
    pageSize,
    total,
    fetchAssets,
    setFilters,
    setPage,
    resetFilters,
  } = useAssetStore();

  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);

  useEffect(() => {
    fetchAssets();
  }, [fetchAssets]);

  const handleSearchChange = useCallback(
    (search: string) => {
      setFilters({ search });
    },
    [setFilters]
  );

  const handleAssetTypeChange = useCallback(
    (assetType: typeof filters.assetType) => {
      setFilters({ assetType });
    },
    [setFilters]
  );

  const handleStateChange = useCallback(
    (state: typeof filters.state) => {
      setFilters({ state });
    },
    [setFilters]
  );

  const handleAssetClick = useCallback((asset: Asset) => {
    setSelectedAsset(asset);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedAsset(null);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Assets</h1>
          <p className="text-gray-400 mt-1">Browse and manage your 3D assets</p>
        </div>
        <button
          onClick={() => setUploadDialogOpen(true)}
          className="px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 4v16m8-8H4"
            />
          </svg>
          Upload Asset
        </button>
      </div>

      <AssetFilters
        search={filters.search}
        assetType={filters.assetType}
        state={filters.state}
        onSearchChange={handleSearchChange}
        onAssetTypeChange={handleAssetTypeChange}
        onStateChange={handleStateChange}
        onReset={resetFilters}
      />

      <AssetGrid
        assets={assets}
        isLoading={isLoading}
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
        onAssetClick={handleAssetClick}
      />

      {selectedAsset && <AssetDetailModal asset={selectedAsset} onClose={handleCloseDetail} />}

      {uploadDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setUploadDialogOpen(false)} />
          <div className="relative bg-gray-900 border border-gray-800 rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
              <h2 className="text-lg font-semibold text-gray-100">Upload Asset</h2>
              <button
                onClick={() => setUploadDialogOpen(false)}
                className="text-gray-500 hover:text-gray-300 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6">
              <div className="border-2 border-dashed border-gray-700 rounded-lg p-8 text-center hover:border-gray-600 transition-colors">
                <svg className="w-12 h-12 text-gray-500 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
                <p className="text-gray-300">
                  <span className="text-blue-400 font-medium cursor-pointer">Click to upload</span> or drag and drop
                </p>
                <p className="text-gray-500 text-sm mt-1">GLB, GLTF, FBX, OBJ, PNG, JPG (max 100MB)</p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-800 bg-gray-900/50">
              <button
                onClick={() => setUploadDialogOpen(false)}
                className="px-4 py-2 text-gray-400 hover:text-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors">
                Upload
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}