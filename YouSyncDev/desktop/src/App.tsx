import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import { SyncStatusProvider } from "./context/SyncStatusContext";
import HomePage from "./pages/HomePage";
import PlaylistsPage from "./pages/PlaylistsPage";
import SettingsPage from "./pages/SettingsPage";

function App() {
  return (
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
  );
}

export default App;
