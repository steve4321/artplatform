import { useState } from 'react';

function AssetsPage() {
  const [search, setSearch] = useState('');

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Assets</h1>
        <p className="text-gray-400 mt-1">Browse and manage your 3D assets</p>
      </div>
      <div className="flex gap-4">
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
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search assets..."
            className="w-full pl-10 pr-4 py-3 bg-gray-900 border border-gray-800 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-primary-600"
          />
        </div>
        <button className="px-4 py-3 bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 rounded-lg transition-colors">
          Filter
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
            <div className="h-40 bg-gray-800 flex items-center justify-center">
              <span className="text-gray-600">Asset {i}</span>
            </div>
            <div className="p-4">
              <h3 className="font-medium text-gray-100">Asset Name {i}</h3>
              <p className="text-sm text-gray-400 mt-1">Character • Model</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default AssetsPage;