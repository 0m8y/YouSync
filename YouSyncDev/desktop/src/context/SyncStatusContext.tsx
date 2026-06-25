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
} from "../services/playlistService";

const SYNC_STATUS_POLL_MS = 1500;

type SyncStatusContextValue = {
  syncProgressById: Record<string, SyncStatus>;
  syncAllProgress: SyncAllStatus | null;
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

export function SyncStatusProvider({ children }: { children: ReactNode }) {
  const [syncProgressById, setSyncProgressById] = useState<Record<string, SyncStatus>>({});
  const [syncAllProgress, setSyncAllProgress] = useState<SyncAllStatus | null>(null);
  const [statusVersion, setStatusVersion] = useState(0);
  const previousActiveIds = useRef<Set<string>>(new Set());

  const refreshSyncStatuses = useCallback(async () => {
    const status = await getSyncTasksStatus();
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
    setSyncProgressById(nextProgressById);
    setSyncAllProgress(status.syncAll ?? null);

    if (completedSinceLastPoll) {
      setStatusVersion((version) => version + 1);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timeoutId: number | null = null;

    async function poll() {
      await refreshSyncStatuses();

      if (!cancelled) {
        timeoutId = window.setTimeout(poll, SYNC_STATUS_POLL_MS);
      }
    }

    void poll();

    return () => {
      cancelled = true;

      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [refreshSyncStatuses]);

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
