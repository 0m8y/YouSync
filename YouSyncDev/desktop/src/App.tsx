import { Navigate, Route, Routes } from "react-router-dom";
import { useEffect } from "react";
import AppShell from "./components/AppShell";
import { ConfirmProvider } from "./components/ConfirmProvider";
import { ToastProvider } from "./components/ToastProvider";
import { SettingsProvider } from "./context/SettingsContext";
import { SyncStatusProvider } from "./context/SyncStatusContext";
import HomePage from "./pages/HomePage";
import PlaylistsPage from "./pages/PlaylistsPage";
import SettingsPage from "./pages/SettingsPage";

function startupLog(message: string) {
  const startupWindow = window as Window & { __YOUSYNC_STARTUP_TIME?: number };
  const startedAt = startupWindow.__YOUSYNC_STARTUP_TIME ?? performance.now();
  console.log(`[startup][react][+${Math.round(performance.now() - startedAt)}ms] ${message}`);
}

function App() {
  useEffect(() => {
    startupLog("App mounted");
  }, []);

  return (
    <ToastProvider>
      <ConfirmProvider>
        <SettingsProvider>
          <SyncStatusProvider>
            <Routes>
              <Route element={<AppShell />}>
                <Route index element={<HomePage />} />
                <Route path="playlists" element={<PlaylistsPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="*" element={<Navigate replace to="/" />} />
              </Route>
            </Routes>
          </SyncStatusProvider>
        </SettingsProvider>
      </ConfirmProvider>
    </ToastProvider>
  );
}

export default App;
