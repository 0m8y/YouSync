import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import { ConfirmProvider } from "./components/ConfirmProvider";
import { ToastProvider } from "./components/ToastProvider";
import { SyncStatusProvider } from "./context/SyncStatusContext";
import HomePage from "./pages/HomePage";
import PlaylistsPage from "./pages/PlaylistsPage";
import SettingsPage from "./pages/SettingsPage";

function App() {
  return (
    <ToastProvider>
      <ConfirmProvider>
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
      </ConfirmProvider>
    </ToastProvider>
  );
}

export default App;
