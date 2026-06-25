import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { DEFAULT_SETTINGS, loadAppSettings, saveAppSettings, type AppSettings } from "../services/settingsService";

type SettingsContextValue = {
  settings: AppSettings;
  updateSettings: (nextSettings: Partial<AppSettings>) => void;
  resetSettings: () => void;
};

const SettingsContext = createContext<SettingsContextValue | null>(null);

function resolveSystemTheme() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(() => loadAppSettings());
  const [systemTheme, setSystemTheme] = useState<"dark" | "light">(() => resolveSystemTheme());

  useEffect(() => {
    if (settings.theme !== "system") {
      return;
    }

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    function handleThemeChange(event: MediaQueryListEvent) {
      setSystemTheme(event.matches ? "dark" : "light");
    }

    setSystemTheme(mediaQuery.matches ? "dark" : "light");
    mediaQuery.addEventListener("change", handleThemeChange);

    return () => {
      mediaQuery.removeEventListener("change", handleThemeChange);
    };
  }, [settings.theme]);

  useEffect(() => {
    document.documentElement.style.setProperty("--ys-accent", settings.accentColor);
  }, [settings.accentColor]);

  useEffect(() => {
    const resolvedTheme = settings.theme === "system" ? systemTheme : settings.theme;
    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.dataset.themeSetting = settings.theme;
  }, [settings.theme, systemTheme]);

  const updateSettings = useCallback((nextSettings: Partial<AppSettings>) => {
    setSettings((currentSettings) => saveAppSettings({ ...currentSettings, ...nextSettings }));
  }, []);

  const resetSettings = useCallback(() => {
    setSettings(saveAppSettings(DEFAULT_SETTINGS));
  }, []);

  const value = useMemo(() => ({
    settings,
    updateSettings,
    resetSettings,
  }), [resetSettings, settings, updateSettings]);

  return (
    <SettingsContext.Provider value={value}>
      {children}
    </SettingsContext.Provider>
  );
}

function useSettings() {
  const context = useContext(SettingsContext);

  if (!context) {
    throw new Error("useSettings must be used inside SettingsProvider.");
  }

  return context;
}

export { SettingsProvider, useSettings };
