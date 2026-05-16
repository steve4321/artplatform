function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Settings</h1>
        <p className="text-gray-400 mt-1">Configure your workspace</p>
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-lg divide-y divide-gray-800">
        <div className="p-6">
          <h2 className="text-lg font-semibold text-gray-100">Account</h2>
          <div className="mt-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-400">Email</label>
              <input
                type="email"
                defaultValue="user@example.com"
                className="mt-1 w-full max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:border-primary-600"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-400">Display Name</label>
              <input
                type="text"
                defaultValue="ArtPlatform User"
                className="mt-1 w-full max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:border-primary-600"
              />
            </div>
          </div>
        </div>
        <div className="p-6">
          <h2 className="text-lg font-semibold text-gray-100">Preferences</h2>
          <div className="mt-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-300">Dark Mode</p>
                <p className="text-sm text-gray-500">Use dark theme</p>
              </div>
              <button className="px-4 py-1.5 bg-primary-600 text-white text-sm rounded-lg">
                Enabled
              </button>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-300">Notifications</p>
                <p className="text-sm text-gray-500">Receive email notifications</p>
              </div>
              <button className="px-4 py-1.5 bg-gray-700 text-gray-300 text-sm rounded-lg">
                Disabled
              </button>
            </div>
          </div>
        </div>
        <div className="p-6">
          <h2 className="text-lg font-semibold text-gray-100">API</h2>
          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-400">API Key</label>
            <div className="mt-1 flex gap-2">
              <input
                type="password"
                readOnly
                defaultValue="sk-artplatform-xxxxxxxxxxxxx"
                className="flex-1 max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100"
              />
              <button className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 rounded-lg transition-colors">
                Regenerate
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SettingsPage;