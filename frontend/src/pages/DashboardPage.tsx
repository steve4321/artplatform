import { useEffect } from 'react';
import { useDashboardStore } from '../stores/dashboardStore';

function DashboardPage() {
  const { stats, recentAssets, isLoading, fetchDashboard } = useDashboardStore();

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Dashboard</h1>
          <p className="text-gray-400 mt-1">Overview of your ArtPlatform workspace</p>
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
        <h1 className="text-2xl font-bold text-gray-100">Dashboard</h1>
        <p className="text-gray-400 mt-1">Overview of your ArtPlatform workspace</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <p className="text-sm text-gray-400">Total Assets</p>
          <p className="text-3xl font-bold text-gray-100 mt-2">{stats.totalAssets}</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <p className="text-sm text-gray-400">Pending Reviews</p>
          <p className="text-3xl font-bold text-gray-100 mt-2">{stats.pendingReviews}</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <p className="text-sm text-gray-400">Active Pipelines</p>
          <p className="text-3xl font-bold text-gray-100 mt-2">{stats.activePipelines}</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <p className="text-sm text-gray-400">Storage Used</p>
          <p className="text-3xl font-bold text-gray-100 mt-2">—</p>
        </div>
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-100 mb-4">Recent Assets</h2>
        {recentAssets.length === 0 ? (
          <p className="text-gray-500">No assets yet</p>
        ) : (
          <div className="space-y-4">
            {recentAssets.map((asset) => (
              <div key={asset.id} className="flex items-center gap-4 text-gray-300">
                <div className="w-2 h-2 rounded-full bg-blue-600" />
                <span>{asset.name}</span>
                <span
                  className={`px-2 py-0.5 text-xs rounded-full ${
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
                  {asset.state}
                </span>
                <span className="text-gray-500 text-sm ml-auto">
                  {new Date(asset.createdAt).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default DashboardPage;