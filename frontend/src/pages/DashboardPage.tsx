interface StatCard {
  label: string;
  value: string;
  change: string;
  changeType: 'positive' | 'negative' | 'neutral';
}

const stats: StatCard[] = [
  { label: 'Total Assets', value: '247', change: '+12%', changeType: 'positive' },
  { label: 'Pending Reviews', value: '8', change: '-3%', changeType: 'positive' },
  { label: 'Active Pipelines', value: '3', change: '0%', changeType: 'neutral' },
  { label: 'Storage Used', value: '142 GB', change: '+5%', changeType: 'negative' },
];

function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Dashboard</h1>
        <p className="text-gray-400 mt-1">Overview of your ArtPlatform workspace</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <div key={stat.label} className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <p className="text-sm text-gray-400">{stat.label}</p>
            <p className="text-3xl font-bold text-gray-100 mt-2">{stat.value}</p>
            <p
              className={`text-sm mt-2 ${
                stat.changeType === 'positive'
                  ? 'text-green-400'
                  : stat.changeType === 'negative'
                  ? 'text-red-400'
                  : 'text-gray-400'
              }`}
            >
              {stat.change}
            </p>
          </div>
        ))}
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-100 mb-4">Recent Activity</h2>
        <div className="space-y-4">
          <div className="flex items-center gap-4 text-gray-300">
            <div className="w-2 h-2 rounded-full bg-green-400" />
            <span>Pipeline #pipeline-abc123 completed successfully</span>
            <span className="text-gray-500 text-sm ml-auto">2 min ago</span>
          </div>
          <div className="flex items-center gap-4 text-gray-300">
            <div className="w-2 h-2 rounded-full bg-primary-600" />
            <span>New asset "Warrior Character" uploaded</span>
            <span className="text-gray-500 text-sm ml-auto">15 min ago</span>
          </div>
          <div className="flex items-center gap-4 text-gray-300">
            <div className="w-2 h-2 rounded-full bg-yellow-400" />
            <span>Review requested for "Forest Environment"</span>
            <span className="text-gray-500 text-sm ml-auto">1 hour ago</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default DashboardPage;