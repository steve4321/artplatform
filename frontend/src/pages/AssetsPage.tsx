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
  const { getDownloadUrl, submitForReview } = useAssetStore();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const latestVersion = asset.versions?.length > 0
    ? asset.versions.reduce((prev, curr) => (curr.version > prev.version ? curr : prev))
    : null;

  const previewUrl = latestVersion
    ? getDownloadUrl(asset.id, latestVersion.version)
    : null;

  const handleSubmitForReview = async () => {
    setIsSubmitting(true);
    try {
      await submitForReview(asset.id);
      onClose();
    } catch (err) {
      console.error('Failed to submit for review:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDownload = () => {
    if (latestVersion) {
      const url = getDownloadUrl(asset.id, latestVersion.version);
      window.open(url, '_blank');
    }
  };

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
              {previewUrl ? (
                <AssetViewer modelUrl={previewUrl} className="w-full h-full" autoPlay />
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
                    {latestVersion && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">Version</span>
                        <span className="text-gray-200">v{latestVersion.version}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Versions</h4>
                  {asset.versions && asset.versions.length > 0 ? (
                    <div className="space-y-2">
                      {asset.versions.slice().reverse().map((v) => (
                        <div key={v.id} className="bg-gray-800 rounded-lg p-3 text-sm">
                          <div className="flex justify-between">
                            <span className="text-gray-200">v{v.version}</span>
                            <span className="text-gray-500">{v.fileFormat}</span>
                          </div>
                          <div className="text-xs text-gray-500 mt-1">
                            {v.fileSizeBytes ? `${Math.round(v.fileSizeBytes / 1024 / 1024)} MB` : 'Unknown size'}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-gray-500 text-sm">No versions available</p>
                  )}
                </div>
              </div>

              <div className="mt-8 flex gap-3">
                <button
                  onClick={handleDownload}
                  disabled={!latestVersion}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium rounded-lg transition-colors"
                >
                  Download
                </button>
                <button className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 font-medium rounded-lg transition-colors">
                  Edit
                </button>
                {asset.state === 'draft' && (
                  <button
                    onClick={handleSubmitForReview}
                    disabled={isSubmitting}
                    className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white font-medium rounded-lg transition-colors"
                  >
                    {isSubmitting ? 'Submitting...' : 'Submit for Review'}
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
    createAsset,
    uploadVersion,
  } = useAssetStore();

  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadName, setUploadName] = useState('');
  const [uploadType, setUploadType] = useState<'model_3d' | 'texture_2d' | 'animation' | 'material'>('model_3d');
  const [isUploading, setIsUploading] = useState(false);

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

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadFile(file);
      if (!uploadName) {
        setUploadName(file.name.replace(/\.[^/.]+$/, ''));
      }
    }
  };

  const handleUpload = async () => {
    if (!uploadFile || !uploadName) return;
    setIsUploading(true);
    try {
      const asset = await createAsset({
        name: uploadName,
        assetType: uploadType,
      });
      await uploadVersion(asset.id, uploadFile);
      await fetchAssets();
      setUploadDialogOpen(false);
      setUploadFile(null);
      setUploadName('');
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setIsUploading(false);
    }
  };

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
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Asset Name</label>
                <input
                  type="text"
                  value={uploadName}
                  onChange={(e) => setUploadName(e.target.value)}
                  placeholder="My 3D Model"
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:border-blue-600"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Asset Type</label>
                <select
                  value={uploadType}
                  onChange={(e) => setUploadType(e.target.value as typeof uploadType)}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:border-blue-600"
                >
                  <option value="model_3d">3D Model</option>
                  <option value="texture_2d">Texture</option>
                  <option value="animation">Animation</option>
                  <option value="material">Material</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">File</label>
                <input
                  type="file"
                  accept=".glb,.gltf,.fbx,.obj,.png,.jpg,.jpeg"
                  onChange={handleFileSelect}
                  className="w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-600 file:text-white file:hover:bg-blue-700 file:cursor-pointer"
                />
                {uploadFile && (
                  <p className="mt-2 text-sm text-gray-400">
                    Selected: {uploadFile.name} ({(uploadFile.size / 1024 / 1024).toFixed(2)} MB)
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-800 bg-gray-900/50">
              <button
                onClick={() => setUploadDialogOpen(false)}
                className="px-4 py-2 text-gray-400 hover:text-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleUpload}
                disabled={!uploadFile || !uploadName || isUploading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium rounded-lg transition-colors"
              >
                {isUploading ? 'Uploading...' : 'Upload'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}