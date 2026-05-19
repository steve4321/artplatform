import { useEffect, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import DashboardPage from './pages/DashboardPage';
import GeneratePage from './pages/GeneratePage';
import AssetsPage from './pages/AssetsPage';
import ReviewsPage from './pages/ReviewsPage';
import SettingsPage from './pages/SettingsPage';
import LoginPage from './pages/LoginPage';
import { useAuthStore } from './stores/authStore';

function AppLayout() {
  return (
    <div className="flex h-screen bg-gray-950">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-6 bg-gray-950">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/generate" element={<GeneratePage />} />
            <Route path="/assets" element={<AssetsPage />} />
            <Route path="/reviews" element={<ReviewsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={
              <div className="flex flex-col items-center justify-center h-full">
                <h1 className="text-4xl font-bold text-gray-100">404</h1>
                <p className="text-gray-400 mt-2">Page not found</p>
                <a href="/dashboard" className="mt-4 text-blue-400 hover:text-blue-300 text-sm">Back to Dashboard</a>
              </div>
            } />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function App() {
  const [isInitialized, setIsInitialized] = useState(false);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    useAuthStore.getState().initializeAuth().finally(() => setIsInitialized(true));
  }, []);

  if (!isInitialized) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-950">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <LoginPage />}
      />
      <Route
        path="/*"
        element={isAuthenticated ? <AppLayout /> : <Navigate to="/login" replace />}
      />
    </Routes>
  );
}

export default App;