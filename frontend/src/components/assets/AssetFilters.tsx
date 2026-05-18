import { useState, useEffect, useCallback } from 'react';
import type { AssetType, State } from '../../types';

interface AssetFiltersProps {
  search: string;
  assetType: AssetType | 'all';
  state: State | 'all';
  onSearchChange: (search: string) => void;
  onAssetTypeChange: (assetType: AssetType | 'all') => void;
  onStateChange: (state: State | 'all') => void;
  onReset: () => void;
}

export function AssetFilters({
  search,
  assetType,
  state,
  onSearchChange,
  onAssetTypeChange,
  onStateChange,
  onReset,
}: AssetFiltersProps) {
  const [localSearch, setLocalSearch] = useState(search);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (localSearch !== search) {
        onSearchChange(localSearch);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [localSearch, search, onSearchChange]);

  const handleReset = useCallback(() => {
    setLocalSearch('');
    onReset();
  }, [onReset]);

  const hasActiveFilters = search || assetType !== 'all' || state !== 'all';

  return (
    <div className="flex flex-col sm:flex-row gap-3">
      <div className="flex-1 relative">
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <input
          type="text"
          value={localSearch}
          onChange={(e) => setLocalSearch(e.target.value)}
          placeholder="Search assets by name..."
          className="w-full pl-10 pr-4 py-3 bg-gray-900 border border-gray-800 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-600 transition-colors"
        />
      </div>

      <select
        value={assetType}
        onChange={(e) => onAssetTypeChange(e.target.value as AssetType | 'all')}
        className="px-4 py-3 bg-gray-900 border border-gray-800 rounded-lg text-gray-300 focus:outline-none focus:border-blue-600 transition-colors cursor-pointer"
      >
        <option value="all">All Types</option>
        <option value="model_3d">3D Models</option>
        <option value="texture_2d">2D Textures</option>
        <option value="animation">Animations</option>
        <option value="material">Materials</option>
      </select>

      <select
        value={state}
        onChange={(e) => onStateChange(e.target.value as State | 'all')}
        className="px-4 py-3 bg-gray-900 border border-gray-800 rounded-lg text-gray-300 focus:outline-none focus:border-blue-600 transition-colors cursor-pointer"
      >
        <option value="all">All States</option>
        <option value="draft">Draft</option>
        <option value="processing">Processing</option>
        <option value="review">In Review</option>
        <option value="approved">Approved</option>
        <option value="published">Published</option>
        <option value="rejected">Rejected</option>
        <option value="deprecated">Deprecated</option>
      </select>

      {hasActiveFilters && (
        <button
          onClick={handleReset}
          className="px-4 py-3 bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 rounded-lg transition-colors"
        >
          Clear
        </button>
      )}
    </div>
  );
}

export default AssetFilters;