import { useCallback, useEffect, useMemo, useState } from "react";
import PlaylistRow from "../components/PlaylistRow";
import Toast from "../components/Toast";
import PlaylistDetailPage from "./PlaylistDetailPage";
import { USE_MOCK_PLAYLIST_STATUSES, mockPlaylists } from "../data/mockPlaylists";
import {
  PLAYLISTS_UPDATED_EVENT,
  cancelPlaylistSync,
  deletePlaylist,
  downloadMissing,
  getSyncAllStatus,
  getSyncStatus,
  listPlaylists,
  syncAllPlaylists,
  syncPlaylist
} from "../services/playlistService";
import type { LongTaskProgress, PlaylistSummary, SyncAllStatus, SyncStatus } from "../services/playlistService";

const SYNC_STATUS_POLL_MS = 1500;

function progressLabel(progress: LongTaskProgress | null) {
  if (!progress) {
    return "";
  }

  const parts = [];
  const message = progress.message || (progress.phase === "downloading" ? "Downloading..." : "Syncing...");

  parts.push(message);

  if (progress.playlistTitle) {
    const playlistIndex =
      progress.playlistCurrent && progress.playlistTotal
        ? "Playlist " + progress.playlistCurrent + "/" + progress.playlistTotal + ": "
        : "";
    parts.push(playlistIndex + progress.playlistTitle);
  }

  if (progress.total && progress.total > 0) {
    parts.push((progress.current ?? 0) + " / " + progress.total);
  }

  if (progress.currentTrack) {
    parts.push("Current: " + progress.currentTrack);
  }

  if (progress.failedCount && progress.failedCount > 0) {
    parts.push(progress.failedCount + " failed");
  }

  return parts.join(" · ");
}

function isActiveProgress(progress?: LongTaskProgress | null) {
  return progress?.status === "syncing" || progress?.phase === "syncing" || progress?.phase === "downloading";
}

function PlaylistsPage() {
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [syncProgressById, setSyncProgressById] = useState<Record<string, SyncStatus>>({});
  const [isSyncingAll, setIsSyncingAll] = useState(false);
  const [syncAllProgress, setSyncAllProgress] = useState<SyncAllStatus | null>(null);
  const [selectedPlaylistId, setSelectedPlaylistId] = useState<string | null>(null);
  const [toast, setToast] = useState("");

  const activeSyncIds = useMemo(
    () => Object.entries(syncProgressById)
      .filter(([, progress]) => isActiveProgress(progress))
      .map(([playlistId]) => playlistId),
    [syncProgressById]
  );
  const activeSyncKey = activeSyncIds.join("|");
  const hasActiveIndividualSyncs = activeSyncIds.length > 0;

  const reloadPlaylists = useCallback(async () => {
    if (USE_MOCK_PLAYLIST_STATUSES) {
      setPlaylists(mockPlaylists);
      return mockPlaylists;
    }

    const nextPlaylists = await listPlaylists();
    setPlaylists(nextPlaylists);
    return nextPlaylists;
  }, []);

  const recoverActiveSync = useCallback(async (playlistsToCheck: PlaylistSummary[]) => {
    if (USE_MOCK_PLAYLIST_STATUSES) {
      setIsSyncingAll(false);
      setSyncProgressById({});
      return;
    }

    const syncAllStatus = await getSyncAllStatus();

    if (syncAllStatus.status === "syncing") {
      setIsSyncingAll(true);
      setSyncProgressById({});
      setSyncAllProgress(syncAllStatus);
      return;
    }

    setIsSyncingAll(false);
    setSyncAllProgress(null);

    const statuses = await Promise.all(
      playlistsToCheck.map(async (playlist) => [playlist.id, await getSyncStatus(playlist.id)] as const)
    );
    const activeStatuses = Object.fromEntries(
      statuses.filter(([, status]) => isActiveProgress(status))
    );

    setSyncProgressById(activeStatuses);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialPlaylists() {
      const nextPlaylists = USE_MOCK_PLAYLIST_STATUSES ? mockPlaylists : await listPlaylists();

      if (cancelled) {
        return;
      }

      console.info("[YouSync] PlaylistsPage initial list", nextPlaylists.map((playlist) => ({
        id: playlist.id,
        title: playlist.title,
        coverPath: playlist.coverPath,
        tracks: playlist.tracks,
        status: playlist.status,
      })));
      setPlaylists(nextPlaylists);
      await recoverActiveSync(nextPlaylists);
    }

    function handlePlaylistsUpdated(event: Event) {
      const updatedPlaylists = (event as CustomEvent<PlaylistSummary[]>).detail;

      if (Array.isArray(updatedPlaylists)) {
        console.info("[YouSync] PlaylistsPage update event", updatedPlaylists.map((playlist) => ({
          id: playlist.id,
          title: playlist.title,
          coverPath: playlist.coverPath,
          tracks: playlist.tracks,
          status: playlist.status,
        })));
        setPlaylists(updatedPlaylists);
        void recoverActiveSync(updatedPlaylists);
        return;
      }

      void reloadPlaylists().then((nextPlaylists) => recoverActiveSync(nextPlaylists));
    }

    void loadInitialPlaylists();
    window.addEventListener(PLAYLISTS_UPDATED_EVENT, handlePlaylistsUpdated);

    return () => {
      cancelled = true;
      window.removeEventListener(PLAYLISTS_UPDATED_EVENT, handlePlaylistsUpdated);
    };
  }, [recoverActiveSync, reloadPlaylists]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timeout = window.setTimeout(() => setToast(""), 3200);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  useEffect(() => {
    if (!isSyncingAll) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    async function pollSyncAllStatus() {
      const status = await getSyncAllStatus();

      if (cancelled) {
        return;
      }

      setSyncAllProgress(status);

      if (status.status === "syncing") {
        timeoutId = window.setTimeout(pollSyncAllStatus, SYNC_STATUS_POLL_MS);
        return;
      }

      if (status.status === "completed") {
        await reloadPlaylists();

        if (!cancelled) {
          if (status.message?.includes("failed")) {
            setToast(status.message);
          }
          setIsSyncingAll(false);
          setSyncAllProgress(null);
        }
        return;
      }

      if (status.status === "error") {
        await reloadPlaylists();

        if (!cancelled) {
          setToast(status.message || "Sync all could not be completed.");
          setIsSyncingAll(false);
          setSyncAllProgress(null);
        }
        return;
      }

      await reloadPlaylists();

      if (!cancelled) {
        setIsSyncingAll(false);
        setSyncAllProgress(null);
      }
    }

    void pollSyncAllStatus().catch((error) => {
      if (!cancelled) {
        setToast(error instanceof Error ? error.message : String(error));
        setIsSyncingAll(false);
        setSyncAllProgress(null);
      }
    });

    return () => {
      cancelled = true;

      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [isSyncingAll, reloadPlaylists]);

  useEffect(() => {
    if (isSyncingAll || !activeSyncKey) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    async function pollSyncStatuses() {
      const playlistIds = activeSyncKey.split("|").filter(Boolean);
      const statuses = await Promise.all(playlistIds.map((playlistId) => getSyncStatus(playlistId)));

      if (cancelled) {
        return;
      }

      const completedOrErrored = statuses.filter((status) => !isActiveProgress(status));
      const stillActive = statuses.filter((status) => isActiveProgress(status));

      setSyncProgressById((current) => {
        const next = { ...current };

        for (const status of statuses) {
          next[status.playlistId] = status;
        }

        return next;
      });

      if (completedOrErrored.length > 0) {
        await reloadPlaylists();
      }

      if (stillActive.length > 0) {
        timeoutId = window.setTimeout(pollSyncStatuses, SYNC_STATUS_POLL_MS);
      }
    }

    void pollSyncStatuses().catch((error) => {
      if (!cancelled) {
        setToast(error instanceof Error ? error.message : String(error));
        setSyncProgressById({});
      }
    });

    return () => {
      cancelled = true;

      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [activeSyncKey, isSyncingAll, reloadPlaylists]);

  useEffect(() => {
    const completedIds = Object.entries(syncProgressById)
      .filter(([, progress]) => progress.status === "completed" || progress.status === "cancelled")
      .map(([playlistId]) => playlistId);

    if (completedIds.length === 0) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setSyncProgressById((current) => {
        const next = { ...current };

        for (const playlistId of completedIds) {
          if (next[playlistId]?.status === "completed" || next[playlistId]?.status === "cancelled") {
            delete next[playlistId];
          }
        }

        return next;
      });
    }, 2800);

    return () => window.clearTimeout(timeout);
  }, [syncProgressById]);

  async function handleSyncPlaylist(playlistId: string) {
    if (isSyncingAll || isActiveProgress(syncProgressById[playlistId])) {
      return;
    }

    setToast("");

    if (USE_MOCK_PLAYLIST_STATUSES) {
      setToast("Mock status mode is enabled.");
      return;
    }

    const startResult = await syncPlaylist(playlistId);

    if (!startResult.started) {
      setToast(startResult.message ?? "A sync is already running.");
      await recoverActiveSync(playlists);
      return;
    }

    setIsSyncingAll(false);
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

  async function handleDownloadMissing(playlistId: string) {
    if (isSyncingAll || isActiveProgress(syncProgressById[playlistId])) {
      return;
    }

    setToast("");

    if (USE_MOCK_PLAYLIST_STATUSES) {
      setToast("Mock status mode is enabled.");
      return;
    }

    const startResult = await downloadMissing(playlistId);

    if (!startResult.started) {
      setToast(startResult.message ?? "A sync or download is already running.");
      await recoverActiveSync(playlists);
      return;
    }

    setIsSyncingAll(false);
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

  async function handleCancelPlaylistSync(playlistId: string) {
    if (!isActiveProgress(syncProgressById[playlistId])) {
      return;
    }

    const result = await cancelPlaylistSync(playlistId);

    if (!result.ok) {
      setToast(result.message);
      return;
    }

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
    await reloadPlaylists();
  }

  async function handleRemovePlaylist(playlistId: string) {
    if (isSyncingAll || hasActiveIndividualSyncs) {
      setToast("Cannot remove playlist while a sync or download is running.");
      return;
    }

    const confirmed = window.confirm(
      "Remove playlist?\n\nThis will remove the playlist from YouSync. Local audio files will not be deleted."
    );

    if (!confirmed) {
      return;
    }

    setToast("");

    if (USE_MOCK_PLAYLIST_STATUSES) {
      setPlaylists((currentPlaylists) => currentPlaylists.filter((playlist) => playlist.id !== playlistId));
      return;
    }

    const result = await deletePlaylist(playlistId);

    if (!result.ok) {
      setToast(result.message);
      await recoverActiveSync(playlists);
      return;
    }

    await reloadPlaylists();
    setToast(result.message);
  }

  async function handleSyncAll() {
    if (hasActiveIndividualSyncs || isSyncingAll || playlists.length === 0) {
      return;
    }

    setToast("");

    if (USE_MOCK_PLAYLIST_STATUSES) {
      setToast("Mock status mode is enabled.");
      return;
    }

    const startResult = await syncAllPlaylists();

    if (!startResult.started) {
      setToast(startResult.message ?? "A sync is already running.");
      await recoverActiveSync(playlists);
      return;
    }

    setSyncProgressById({});
    setIsSyncingAll(true);
    setSyncAllProgress({
      playlistIds: startResult.playlistIds,
      status: "syncing",
      phase: "syncing",
      message: "Syncing playlists...",
      playlistCurrent: 0,
      playlistTotal: startResult.playlistIds.length,
      playlists: Object.fromEntries(
        startResult.playlistIds.map((playlistId) => [
          playlistId,
          {
            status: "queued",
            phase: "queued",
            current: 0,
            total: 0,
            failedCount: 0,
            message: "Queued",
          },
        ]),
      ),
    });
  }

  const syncedCount = playlists.filter((playlist) => playlist.status.type === "synced").length;
  const syncAllDisabled = hasActiveIndividualSyncs || isSyncingAll || playlists.length === 0;
  const playlistProgress = (playlistId: string): LongTaskProgress | null => {
    if (syncProgressById[playlistId]) {
      return syncProgressById[playlistId];
    }

    if (isSyncingAll) {
      return syncAllProgress?.playlists?.[playlistId] ?? null;
    }

    return null;
  };

  if (selectedPlaylistId) {
    return (
      <PlaylistDetailPage
        playlistId={selectedPlaylistId}
        onBack={() => {
          setSelectedPlaylistId(null);
          void reloadPlaylists();
        }}
      />
    );
  }

  return (
    <section className="playlists-page" aria-labelledby="playlists-title">
      <header className="playlists-topbar">
        <h1 id="playlists-title">Playlists</h1>
        <p>{playlists.length} playlists · {syncedCount} synced</p>

        <div className="topbar-actions">
          <button type="button" disabled={syncAllDisabled} onClick={handleSyncAll}>
            {isSyncingAll ? "↻ Syncing..." : "↻ Sync all"}
          </button>
          <button type="button">＋ Add playlist</button>
        </div>

        {isSyncingAll && syncAllProgress ? (
          <div className="topbar-progress" role="status">
            <span className="sync-spinner" aria-hidden="true" />
            <span>{progressLabel(syncAllProgress)}</span>
          </div>
        ) : null}
      </header>

      <div className="playlists-content">
        <div className="playlist-table-header" aria-hidden="true">
          <span />
          <span>Name</span>
          <span>Platform</span>
          <span>Tracks</span>
          <span>Status</span>
          <span>Last Synced</span>
          <span />
        </div>

        <div className="playlist-list">
          {playlists.map((playlist) => {
            const rowProgress = playlistProgress(playlist.id);

            return (
              <PlaylistRow
                key={playlist.id}
                playlist={playlist}
                isSyncing={isActiveProgress(rowProgress)}
                progress={rowProgress}
                onOpen={setSelectedPlaylistId}
                onSync={handleSyncPlaylist}
                onCancelSync={handleCancelPlaylistSync}
                onDownloadMissing={handleDownloadMissing}
                onRemove={handleRemovePlaylist}
              />
            );
          })}
        </div>
      </div>

      {toast ? <Toast message={toast} /> : null}
    </section>
  );
}

export default PlaylistsPage;
