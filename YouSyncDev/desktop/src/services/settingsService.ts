export type AudioQuality = "low" | "medium" | "high";
export type AppTheme = "system" | "dark" | "light";

export type AppSettings = {
  defaultPlaylistFolder: string | null;
  maxParallelDownloads: number;
  audioQuality: AudioQuality;
  debugLogsEnabled: boolean;
  accentColor: string;
  theme: AppTheme;
  autoSyncAfterAdd: boolean;
};

const SETTINGS_STORAGE_KEY = "yousync:settings";

export const DEFAULT_SETTINGS: AppSettings = {
  defaultPlaylistFolder: null,
  maxParallelDownloads: 3,
  audioQuality: "high",
  debugLogsEnabled: false,
  accentColor: "#3a7d5a",
  theme: "system",
  autoSyncAfterAdd: false,
};

const AUDIO_QUALITIES: AudioQuality[] = ["low", "medium", "high"];
const APP_THEMES: AppTheme[] = ["system", "dark", "light"];

function clampParallelDownloads(value: unknown) {
  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return DEFAULT_SETTINGS.maxParallelDownloads;
  }

  return Math.min(5, Math.max(1, Math.round(parsed)));
}

export function sanitizeSettings(rawSettings: unknown): AppSettings {
  if (!rawSettings || typeof rawSettings !== "object") {
    return DEFAULT_SETTINGS;
  }

  const settings = rawSettings as Partial<AppSettings>;
  const audioQuality = AUDIO_QUALITIES.includes(settings.audioQuality as AudioQuality)
    ? settings.audioQuality as AudioQuality
    : DEFAULT_SETTINGS.audioQuality;
  const theme = APP_THEMES.includes(settings.theme as AppTheme)
    ? settings.theme as AppTheme
    : DEFAULT_SETTINGS.theme;

  return {
    defaultPlaylistFolder: typeof settings.defaultPlaylistFolder === "string" && settings.defaultPlaylistFolder.trim()
      ? settings.defaultPlaylistFolder
      : null,
    maxParallelDownloads: clampParallelDownloads(settings.maxParallelDownloads),
    audioQuality,
    debugLogsEnabled: Boolean(settings.debugLogsEnabled),
    accentColor: typeof settings.accentColor === "string" && settings.accentColor.trim()
      ? settings.accentColor
      : DEFAULT_SETTINGS.accentColor,
    theme,
    autoSyncAfterAdd: Boolean(settings.autoSyncAfterAdd),
  };
}

export function loadAppSettings(): AppSettings {
  try {
    const rawSettings = window.localStorage.getItem(SETTINGS_STORAGE_KEY);

    if (!rawSettings) {
      return DEFAULT_SETTINGS;
    }

    return sanitizeSettings(JSON.parse(rawSettings));
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveAppSettings(settings: AppSettings) {
  const sanitizedSettings = sanitizeSettings(settings);
  window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(sanitizedSettings));
  return sanitizedSettings;
}

export function debugLog(...args: unknown[]) {
  if (import.meta.env.DEV && loadAppSettings().debugLogsEnabled) {
    console.info(...args);
  }
}

// TODO: Wire audioQuality and maxParallelDownloads into the Python worker once
// the sync/download command payloads accept app settings.
