interface WireframeToggleProps {
  isEnabled: boolean;
  onToggle: (enabled: boolean) => void;
}

export function WireframeToggle({ isEnabled, onToggle }: WireframeToggleProps) {
  return (
    <button
      onClick={() => onToggle(!isEnabled)}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-all duration-200 ${
        isEnabled
          ? 'bg-blue-600 text-white'
          : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200'
      }`}
      title="Toggle wireframe mode"
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M4 6l16 0m-15 5l15 0M4 12l15 0M4 18l15 0"
        />
      </svg>
      <span className="text-sm font-medium">Wireframe</span>
    </button>
  );
}

export default WireframeToggle;