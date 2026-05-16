interface ModelInfoProps {
  polyCount: number;
  textureCount: number;
  boneCount: number;
  fileSize: string;
}

export function ModelInfo({ polyCount, textureCount, boneCount, fileSize }: ModelInfoProps) {
  return (
    <div className="absolute top-4 left-4 bg-gray-900/90 backdrop-blur-sm border border-gray-800 rounded-lg p-3 space-y-2">
      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Model Info</h4>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <span className="text-gray-500">Polygons</span>
        <span className="text-gray-200 font-medium">{polyCount.toLocaleString()}</span>
        <span className="text-gray-500">Textures</span>
        <span className="text-gray-200 font-medium">{textureCount}</span>
        <span className="text-gray-500">Bones</span>
        <span className="text-gray-200 font-medium">{boneCount}</span>
        <span className="text-gray-500">Size</span>
        <span className="text-gray-200 font-medium">{fileSize}</span>
      </div>
    </div>
  );
}

export default ModelInfo;