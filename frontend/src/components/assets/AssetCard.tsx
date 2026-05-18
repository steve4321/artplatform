import { useState } from 'react';
import { Asset } from '../../stores/assetStore';

interface AssetCardProps {
  asset: Asset;
  onClick: (asset: Asset) => void;
}

const stateColors: Record<string, string> = {
  draft: 'bg-gray-600',
  processing: 'bg-blue-600',
  review: 'bg-yellow-600',
  approved: 'bg-green-600',
  published: 'bg-emerald-600',
  deprecated: 'bg-red-600',
  rejected: 'bg-red-600',
};

const stateTextColors: Record<string, string> = {
  draft: 'text-gray-300',
  processing: 'text-blue-300',
  review: 'text-yellow-300',
  approved: 'text-green-300',
  published: 'text-emerald-300',
  deprecated: 'text-red-300',
  rejected: 'text-red-300',
};

const typeLabels: Record<string, string> = {
  model_3d: '3D Model',
  texture_2d: '2D Texture',
  animation: 'Animation',
  material: 'Material',
  sprite: 'Sprite',
};

function getThumbnailUrl(asset: Asset): string | null {
  const latestVersion = asset.versions?.[asset.versions.length - 1];
  return latestVersion?.storageKeyThumbnail ?? null;
}

export function AssetCard({ asset, onClick }: AssetCardProps) {
  const [imageError, setImageError] = useState(false);
  const thumbnailUrl = getThumbnailUrl(asset);

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div
      onClick={() => onClick(asset)}
      className="group bg-gray-900 border border-gray-800 rounded-lg overflow-hidden cursor-pointer transition-all duration-200 hover:border-gray-700 hover:shadow-lg hover:shadow-blue-900/10 hover:-translate-y-1"
    >
      <div className="relative h-44 bg-gray-800 flex items-center justify-center overflow-hidden">
        {thumbnailUrl && !imageError ? (
          <img
            src={thumbnailUrl}
            alt={asset.name}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="flex flex-col items-center gap-2 text-gray-600">
            <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
              />
            </svg>
            <span className="text-xs uppercase tracking-wider">{typeLabels[asset.assetType] || asset.assetType}</span>
          </div>
        )}
        <div className="absolute top-2 right-2">
          <span className={`px-2 py-1 text-xs font-medium rounded-full ${stateColors[asset.state]} ${stateTextColors[asset.state]}`}>
            {asset.state.replace('_', ' ')}
          </span>
        </div>
      </div>

      <div className="p-4">
        <h3 className="font-semibold text-gray-100 truncate" title={asset.name}>
          {asset.name}
        </h3>
        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-gray-500">{typeLabels[asset.assetType]}</span>
          <span className="text-xs text-gray-500">{formatDate(asset.createdAt)}</span>
        </div>
      </div>
    </div>
  );
}

export default AssetCard;