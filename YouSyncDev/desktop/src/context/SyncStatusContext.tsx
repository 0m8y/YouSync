import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  cancelPlaylistSync as cancelPlaylistSyncService,
  cancelSyncAll as cancelSyncAllService,
  downloadMissing as downloadMissingService,
  getSyncTasksStatus,
  syncAllPlaylists,
  syncPlaylist as syncPlaylistService,
} from "../services/playlistService";
import type {
  CancelPlaylistSyncResult,
  CancelSyncAllResult,
  LongTaskProgress,
  SyncAllStartResult,
  SyncAllStatus,
  SyncStartResult,
  SyncStatus,
  SyncTasksStatus,
} from "../services/playlistService";

const SYNC_STATUS_POLL_MS = 1500;

type WorkerConnectionState = "idle" | "starting" | "ready" | "error";

type SyncStatusContextValue = {
  syncProgressById: Record<string, SyncStatus>;
  syncAllProgress: SyncAllStatus | null;
  workerState: WorkerConnectionState;
  isSyncingAll: boolean;
  hasActiveIndividualSyncs: boolean;
  statusVersion: number;
  isActiveProgress: (progress?: LongTaskProgress | null) => boolean;
  getPlaylistProgress: (playlistId: string) => SyncStatus | LongTaskProgress | null;
  refreshSyncStatuses: () => Promise<void>;
  syncPlaylist: (playlistId: string) => Promise<SyncStartResult>;
  downloadMissing: (playlistId: string) => Promise<SyncStartResult>;
  cancelPlaylistSync: (playlistId: string) => Promise<CancelPlaylistSyncResult>;
  syncAll: () => Promise<SyncAllStartResult>;
  cancelSyncAll: () => Promise<CancelSyncAllResult>;
};

const SyncStatusContext = createContext<SyncStatusContextValue | null>(null);

function isActiveProgress(progress?: LongTaskProgress | null) {
  return progress?.status === "syncing" || progress?.phase === "syncing" || progress?.phase === "downloading";
}

function isTerminalProgress(progress?: LongTaskProgress | null) {
  return progress?.status === "completed" || progress?.status === "cancelled" || progress?.status === "error";
}

function startupLog(message: string) {
  const startupWindow = window as Window & { __YOUSYNC_STARTUP_TIME?: number };
  const startedAt = startupWindow.__YOUSYNC_STARTUP_TIME ?? performance.now();
  console.log(`[startup][react][+${Math.round(performance.now() - startedAt)}ms] ${message}`);
}

export function SyncStatusProvider({ children }: { children: ReactNode }) {
  const [syncProgressById, setSyncProgressById] = useState<Record<string, SyncStatus>>({});
  const [syncAllProgress, setSyncAllProgress] = useState<SyncAllStatus | null>(null);
  const [workerState, setWorkerState] = useState<WorkerConnectionState>("idle");
  const [pollingEnabled, setPollingEnabled] = useState(false);
  const [statusVersion, setStatusVersion] = useState(0);
  const previousActiveIds = useRef<Set<string>>(new Set());
  const hasActiveTasksRef = useRef(false);

  const refreshSyncStatuses = useCallback(async () => {
    startupLog("getSyncTasksStatus start");
    setWorkerState((state) => (state === "ready" ? state : "starting"));
    let status: SyncTasksStatus;

    try {
      status = await getSyncTasksStatus();
      setWorkerState("ready");
      startupLog("getSyncTasksStatus complete");
    } catch {
      setWorkerState("error");
      startupLog("getSyncTasksStatus failed");
      return;
    }

    const nextProgressById = status.playlists ?? {};
    const nextActiveIds = new Set(
      Object.entries(nextProgressById)
        .filter(([, progress]) => isActiveProgress(progress))
        .map(([playlistId]) => playlistId)
    );
    const completedSinceLastPoll = [...previousActiveIds.current].some(
      (playlistId) => !nextActiveIds.has(playlistId) && isTerminalProgress(nextProgressById[playlistId])
    );

    previousActiveIds.current = nextActiveIds;
    const hasActiveTasks = nextActiveIds.size > 0 || isActiveProgress(status.syncAll ?? null);
    hasActiveTasksRef.current = hasActiveTasks;
    setSyncProgressById(nextProgressById);
    setSyncAllProgress(status.syncAll ?? null);

    if (hasActiveTasks) {
      setPollingEnabled(true);
    }

    if (completedSinceLastPoll) {
      setStatusVersion((version) => version + 1);
    }
  }, []);

  useEffect(() => {
    startupLog("SyncStatusProvider mounted");
  }, []);

  useEffect(() => {
    if (!pollingEnabled) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;
    startupLog("SyncStatusProvider polling started");

    async function poll() {
      await refreshSyncStatuses();

      if (cancelled) {
        return;
      }

      if (hasActiveTasksRef.current) {
        timeoutId = window.setTimeout(poll, SYNC_STATUS_POLL_MS);
      } else {
        setPollingEnabled(false);
      }
    }

    timeoutId = window.setTimeout(poll, 0);

    return () => {
      cancelled = true;

      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [pollingEnabled, refreshSyncStatuses]);

  useEffect(() => {
    const clearableIds = Object.entries(syncProgressById)
      .filter(([, progress]) => progress.status === "completed" || progress.status === "cancelled")
      .map(([playlistId]) => playlistId);

    if (clearableIds.length === 0) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setSyncProgressById((current) => {
        const next = { ...current };

        for (const playlistId of clearableIds) {
          if (next[playlistId]?.status === "completed" || next[playlistId]?.status === "cancelled") {
            delete next[playlistId];
          }
        }

        return next;
      });
    }, 2800);

    return () => window.clearTimeout(timeout);
  }, [syncProgressById]);

  useEffect(() => {
    if (syncAllProgress?.status !== "cancelled" && syncAllProgress?.status !== "completed") {
      return;
    }

    const timeout = window.setTimeout(() => setSyncAllProgress(null), 2800);
    return () => window.clearTimeout(timeout);
  }, [syncAllProgress]);

  const syncPlaylist = useCallback(async (playlistId: string) => {
    const result = await syncPlaylistService(playlistId);

    if (result.started) {
      hasActiveTasksRef.current = true;
      setWorkerState("ready");
      setPollingEnabled(true);
      setSyncProgressById((current) => ({
        ...current,
        [playlistId]: {
          playlistId,
          status: "syncing",
          phase: "syncing",
          message: "Syncing playlist...",
        },
      }));
    }

    return result;
  }, []);

  const downloadMissing = useCallback(async (playlistId: string) => {
    const result = await downloadMissingService(playlistId);

    if (result.started) {
      hasActiveTasksRef.current = true;
      setWorkerState("ready");
      setPollingEnabled(true);
      setSyncProgressById((current) => ({
        ...current,
        [playlistId]: {
          playlistId,
          status: "syncing",
          phase: "downloading",
          message: "Preparing downloads...",
        },
      }));
    }

    return result;
  }, []);

  const cancelPlaylistSync = useCallback(async (playlistId: string) => {
    const result = await cancelPlaylistSyncService(playlistId);

    if (result.ok) {
      setSyncProgressById((current) => ({
        ...current,
        [playlistId]: {
          ...(current[playlistId] ?? { playlistId }),
          playlistId,
          status: "cancelled",
          phase: "cancelled",
          currentTrack: "",
          message: result.message || "Sync cancelled.",
        },
      }));
      await refreshSyncStatuses();
      setStatusVersion((version) => version + 1);
    }

    return result;
  }, [refreshSyncStatuses]);

  const syncAll = useCallback(async () => {
    const result = await syncAllPlaylists();

    if (result.started) {
      hasActiveTasksRef.current = true;
      setWorkerState("ready");
      setPollingEnabled(true);
      setSyncAllProgress({
        playlistIds: result.playlistIds,
        status: "syncing",
        phase: "syncing",
        message: "Syncing playlists...",
        playlistCurrent: 0,
        playlistTotal: result.playlistIds.length,
        playlists: Object.fromEntries(
          result.playlistIds.map((playlistId) => [
            playlistId,
            {
              status: "syncing",
              phase: "syncing",
              current: 0,
              total: 0,
              failedCount: 0,
              message: "Syncing playlist...",
            },
          ])
        ),
      });
      await refreshSyncStatuses();
    }

    return result;
  }, [refreshSyncStatuses]);

  const cancelSyncAll = useCallback(async () => {
    const result = await cancelSyncAllService();

    if (result.ok) {
      setSyncAllProgress((current) => ({
        ...(current ?? {
          playlistIds: [],
          jobType: "all",
          status: "syncing",
          phase: "syncing",
          message: "Syncing playlists...",
        }),
        status: "cancelled",
        phase: "cancelled",
        currentTrack: "",
        message: result.message || "Sync all cancelled.",
      }));
      await refreshSyncStatuses();
      setStatusVersion((version) => version + 1);
    }

    return result;
  }, [refreshSyncStatuses]);

  const activeSyncIds = useMemo(
    () => Object.entries(syncProgressById)
      .filter(([, progress]) => isActiveProgress(progress))
      .map(([playlistId]) => playlistId),
    [syncProgressById]
  );
  const hasActiveIndividualSyncs = activeSyncIds.length > 0;
  const isSyncingAll = syncAllProgress?.jobType === "all" && isActiveProgress(syncAllProgress);

  const getPlaylistProgress = useCallback((playlistId: string) => {
    return syncProgressById[playlistId] ?? syncAllProgress?.playlists?.[playlistId] ?? null;
  }, [syncAllProgress?.playlists, syncProgressById]);

  const value = useMemo<SyncStatusContextValue>(() => ({
    syncProgressById,
    syncAllProgress,
    workerState,
    isSyncingAll,
    hasActiveIndividualSyncs,
    statusVersion,
    isActiveProgress,
    getPlaylistProgress,
    refreshSyncStatuses,
    syncPlaylist,
    downloadMissing,
    cancelPlaylistSync,
    syncAll,
    cancelSyncAll,
  }), [
    cancelPlaylistSync,
    cancelSyncAll,
    downloadMissing,
    getPlaylistProgress,
    hasActiveIndividualSyncs,
    isSyncingAll,
    refreshSyncStatuses,
    statusVersion,
    syncAll,
    syncAllProgress,
    syncPlaylist,
    syncProgressById,
    workerState,
  ]);

  return (
    <SyncStatusContext.Provider value={value}>
      {children}
    </SyncStatusContext.Provider>
  );
}

export function useSyncStatus() {
  const context = useContext(SyncStatusContext);

  if (!context) {
    throw new Error("useSyncStatus must be used inside SyncStatusProvider.");
  }

  return context;
}
