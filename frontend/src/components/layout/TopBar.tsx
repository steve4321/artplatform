import { useLocation } from 'react-router-dom';

const routeNames: Record<string, string> = {
  dashboard: 'Dashboard',
  generate: 'Generate',
  assets: 'Assets',
  reviews: 'Reviews',
  settings: 'Settings',
};

function TopBar() {
  const location = useLocation();
  const currentPath = location.pathname.replace('/', '') || 'dashboard';
  const currentName = routeNames[currentPath] || 'Dashboard';

  return (
    <header className="h-16 flex items-center justify-between px-6 bg-gray-900 border-b border-gray-800">
      <div className="flex items-center gap-4">
        <button className="md:hidden p-2 text-gray-400 hover:text-gray-100">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <h2 className="text-lg font-semibold text-gray-100">{currentName}</h2>
      </div>
      <div className="flex items-center gap-4">
        <button className="p-2 text-gray-400 hover:text-gray-100">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
        </button>
        <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center">
          <span className="text-sm font-medium text-white">U</span>
        </div>
      </div>
    </header>
  );
}

export default TopBar;