import { useState } from 'react';

function GeneratePage() {
  const [prompt, setPrompt] = useState('');

  return (
    <div className="h-full flex flex-col lg:flex-row gap-6">
      <div className="flex-1 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Generate Assets</h1>
          <p className="text-gray-400 mt-1">Create 3D assets from text prompts</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-gray-300">Prompt</span>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="A medieval warrior character with sword and shield, game-ready topology..."
              className="mt-2 w-full h-32 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-primary-600 resize-none"
            />
          </label>
          <button className="px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white font-medium rounded-lg transition-colors">
            Generate
          </button>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-100 mb-4">Pipeline Timeline</h2>
          <div className="flex items-center justify-center h-32 text-gray-500">
            Pipeline steps will appear here
          </div>
        </div>
      </div>
      <div className="lg:w-96 bg-gray-900 border border-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-100 mb-4">3D Preview</h2>
        <div className="flex items-center justify-center h-64 bg-gray-800 rounded-lg border-2 border-dashed border-gray-700 text-gray-500">
          3D Preview
        </div>
      </div>
    </div>
  );
}

export default GeneratePage;