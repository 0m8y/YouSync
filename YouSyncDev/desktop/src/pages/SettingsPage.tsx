import { open } from "@tauri-apps/plugin-dialog";
import type { CSSProperties } from "react";
import { useSettings } from "../context/SettingsContext";
import { useToast } from "../components/ToastProvider";
import { openLogsFolder, openPlaylistsJson } from "../services/playlistService";
import type { AppTheme, AudioQuality } from "../services/settingsService";

const ACCENT_COLORS = [
  { label: "Green", value: "#3a7d5a" },
  { label: "Blue", value: "#4f7dd6" },
  { label: "Rose", value: "#c86b8d" },
  { label: "Amber", value: "#c8944a" },
];

const AUDIO_QUALITY_OPTIONS: Array<{ label: string; value: AudioQuality }> = [
  { label: "Low", value: "low" },
  { label: "Medium", value: "medium" },
  { label: "High", value: "high" },
];

const THEME_OPTIONS: Array<{ label: string; value: AppTheme }> = [
  { label: "System", value: "system" },
  { label: "Dark", value: "dark" },
  { label: "Light", value: "light" },
];

function SettingsPage() {
  const { settings, updateSettings, resetSettings } = useSettings();
  const { showToast } = useToast();

  async function handleChooseDefaultFolder() {
    let selectedFolder: string | string[] | null;

    try {
      selectedFolder = await open({
        directory: true,
        multiple: false,
        title: "Choose default playlist folder",
      });
    } catch {
      showToast("Folder picker could not be opened.", "error");
      return;
    }

    const folder = Array.isArray(selectedFolder) ? selectedFolder[0] : selectedFolder;

    if (!folder) {
      return;
    }

    updateSettings({ defaultPlaylistFolder: folder });
    showToast("Default playlist folder saved.", "success");
  }

  async function handleOpenPlaylistsJson() {
    const opened = await openPlaylistsJson();

    if (opened) {
      showToast("Opening playlists.json.", "success");
      return;
    }

    showToast("playlists.json could not be opened.", "error");
  }

  async function handleOpenLogsFolder() {
    const logsPath = await openLogsFolder();

    if (logsPath) {
      showToast("Opening logs folder.", "success");
      return;
    }

    showToast("Logs folder could not be opened.", "error");
  }

  function handleMaxParallelDownloads(value: string) {
    updateSettings({ maxParallelDownloads: Number(value) });
  }

  function handleResetSettings() {
    resetSettings();
    showToast("Settings reset.", "success");
  }

  return (
    <section className="playlists-page settings-page" aria-labelledby="settings-title">
      <header className="playlists-topbar">
        <h1 id="settings-title">Settings</h1>
        <p>Preferences</p>
      </header>

      <div className="settings-content">
        <section className="settings-section" aria-labelledby="storage-settings-title">
          <div>
            <h2 id="storage-settings-title">Storage</h2>
            <p>Choose where new playlists should be saved by default.</p>
          </div>

          <div className="settings-control">
            <label>Default playlist folder</label>
            <div className="settings-folder-row">
              <code>{settings.defaultPlaylistFolder || "No default folder selected"}</code>
              <button type="button" onClick={handleChooseDefaultFolder}>
                Browse
              </button>
              {settings.defaultPlaylistFolder ? (
                <button type="button" onClick={() => updateSettings({ defaultPlaylistFolder: null })}>
                  Clear
                </button>
              ) : null}
            </div>
          </div>

          <div className="settings-control">
            <label>playlists.json</label>
            <button className="settings-inline-button" type="button" onClick={handleOpenPlaylistsJson}>
              Open playlists.json
            </button>
          </div>
        </section>

        <section className="settings-section" aria-labelledby="sync-settings-title">
          <div>
            <h2 id="sync-settings-title">Sync</h2>
            <p>Keep network usage predictable while downloading tracks.</p>
          </div>

          <div className="settings-control">
            <label htmlFor="max-parallel-downloads">Max parallel downloads</label>
            <div className="settings-range-row">
              <input
                id="max-parallel-downloads"
                type="range"
                min="1"
                max="5"
                step="1"
                value={settings.maxParallelDownloads}
                onChange={(event) => handleMaxParallelDownloads(event.target.value)}
              />
              <strong>{settings.maxParallelDownloads}</strong>
            </div>
            <p className="settings-hint">
              Saved now. Download worker wiring remains capped internally until the Python command accepts this setting.
            </p>
          </div>

          <label className="settings-toggle">
            <input
              type="checkbox"
              checked={settings.autoSyncAfterAdd}
              onChange={(event) => updateSettings({ autoSyncAfterAdd: event.target.checked })}
            />
            <span>
              <strong>Auto sync after adding playlist</strong>
              <em>Open the new playlist detail page and start syncing it automatically.</em>
            </span>
          </label>
        </section>

        {/* <section className="settings-section" aria-labelledby="audio-settings-title">
          <div>
            <h2 id="audio-settings-title">Audio</h2>
            <p>Persist quality preferences for future download wiring.</p>
          </div>

          <div className="settings-control">
            <label>Audio quality</label>
            <div className="settings-segmented">
              {AUDIO_QUALITY_OPTIONS.map((option) => (
                <button
                  className={settings.audioQuality === option.value ? "active" : ""}
                  key={option.value}
                  type="button"
                  onClick={() => updateSettings({ audioQuality: option.value })}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <p className="settings-hint">
              Saved only for now. No bitrate behavior is faked in the UI.
            </p>
          </div>
        </section> */}

        <section className="settings-section" aria-labelledby="appearance-settings-title">
          <div>
            <h2 id="appearance-settings-title">Appearance</h2>
            <p>Choose the app theme and a subtle accent color.</p>
          </div>

          <div className="settings-control">
            <label>Theme</label>
            <div className="settings-segmented">
              {THEME_OPTIONS.map((option) => (
                <button
                  className={settings.theme === option.value ? "active" : ""}
                  key={option.value}
                  type="button"
                  onClick={() => updateSettings({ theme: option.value })}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="settings-control">
            <label>Accent color</label>
            <div className="settings-swatches">
              {ACCENT_COLORS.map((color) => (
                <button
                  className={settings.accentColor === color.value ? "active" : ""}
                  key={color.value}
                  type="button"
                  title={color.label}
                  aria-label={color.label}
                  style={{ "--swatch-color": color.value } as CSSProperties}
                  onClick={() => updateSettings({ accentColor: color.value })}
                />
              ))}
            </div>
          </div>
        </section>

        <section className="settings-section" aria-labelledby="developer-settings-title">
          <div>
            <h2 id="developer-settings-title">Developer</h2>
            <p>Keep frontend debug output quiet unless you need it.</p>
          </div>

          <label className="settings-toggle">
            <input
              type="checkbox"
              checked={settings.debugLogsEnabled}
              onChange={(event) => updateSettings({ debugLogsEnabled: event.target.checked })}
            />
            <span>
              <strong>Enable debug logs</strong>
              <em>Only extra frontend debug logs are controlled by this setting.</em>
            </span>
          </label>

          <div className="settings-control">
            <label>Logs folder</label>
            <button className="settings-inline-button" type="button" onClick={handleOpenLogsFolder}>
              Open logs folder
            </button>
            <p className="settings-hint">
              Persistent logs are stored in ~/Library/Logs/YouSync on macOS. Runtime jobs stay in /tmp/yousync_jobs.
            </p>
          </div>

          <button className="settings-inline-button" type="button" onClick={handleResetSettings}>
            Reset settings
          </button>
        </section>
      </div>
    </section>
  );
}

export default SettingsPage;
