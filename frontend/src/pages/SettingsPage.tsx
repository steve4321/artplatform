import { useAuthStore } from '../stores/authStore';

function SettingsPage() {
  const { user } = useAuthStore();

  if (!user) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Settings</h1>
          <p className="text-gray-400 mt-1">Configure your workspace</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center">
          <p className="text-gray-500">Loading user info...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Settings</h1>
        <p className="text-gray-400 mt-1">Account information</p>
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-lg divide-y divide-gray-800">
        <div className="p-6">
          <h2 className="text-lg font-semibold text-gray-100">Account</h2>
          <div className="mt-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-400">Email</label>
              <p className="mt-1 w-full max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100">
                {user.email}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-400">Display Name</label>
              <p className="mt-1 w-full max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100">
                {user.displayName}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-400">Role</label>
              <span className="mt-1 inline-block px-3 py-1 bg-blue-900/50 text-blue-400 text-sm font-medium rounded-full">
                {user.role}
              </span>
            </div>
            {user.teamId && (
              <div>
                <label className="block text-sm font-medium text-gray-400">Team ID</label>
                <p className="mt-1 w-full max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 font-mono text-sm">
                  {user.teamId}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default SettingsPage;