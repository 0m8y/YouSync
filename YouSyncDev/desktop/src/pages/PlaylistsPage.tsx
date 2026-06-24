import { useCallback, useEffect, useState } from "react";
import PlaylistRow from "../components/PlaylistRow";
import Toast from "../components/Toast";
import {
  PLAYLISTS_UPDATED_EVENT,
  getSyncAllStatus,
  getSyncStatus,
  listPlaylists,
  syncAllPlaylists,
  syncPlaylist
} from "../services/playlistService";
import type { PlaylistSummary } from "../services/playlistService";

const SYNC_STATUS_POLL_MS = 1500;

function PlaylistsPage() {
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [isSyncingAll, setIsSyncingAll] = useState(false);
  const [toast, setToast] = useState("");

  const reloadPlaylists = useCallback(async () => {
    const nextPlaylists = await listPlaylists();
    setPlaylists(nextPlaylists);
    return nextPlaylists;
  }, []);

  const findActiveSyncId = useCallback(async (playlistsToCheck: PlaylistSummary[]) => {
    for (const playlist of playlistsToCheck) {
      const status = await getSyncStatus(playlist.id);

      if (status.status === "syncing") {
        return playlist.id;
      }
    }

    return null;
  }, []);

  const recoverActiveSync = useCallback(async (playlistsToCheck: PlaylistSummary[]) => {
    const syncAllStatus = await getSyncAllStatus();

    if (syncAllStatus.status === "syncing") {
      setIsSyncingAll(true);
      setSyncingId(null);
      return;
    }

    setIsSyncingAll(false);
    const activeSyncId = await findActiveSyncId(playlistsToCheck);
    setSyncingId(activeSyncId);
  }, [findActiveSyncId]);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialPlaylists() {
      const nextPlaylists = await listPlaylists();

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

      const syncAllStatus = await getSyncAllStatus();

      if (cancelled) {
        return;
      }

      if (syncAllStatus.status === "syncing") {
        setIsSyncingAll(true);
        setSyncingId(null);
        return;
      }

      setIsSyncingAll(false);
      const activeSyncId = await findActiveSyncId(nextPlaylists);

      if (!cancelled) {
        setSyncingId(activeSyncId);
      }
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
  }, [findActiveSyncId, recoverActiveSync, reloadPlaylists]);

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

      if (status.status === "syncing") {
        timeoutId = window.setTimeout(pollSyncAllStatus, SYNC_STATUS_POLL_MS);
        return;
      }

      if (status.status === "completed") {
        await reloadPlaylists();

        if (!cancelled) {
          setIsSyncingAll(false);
          setSyncingId(null);
        }
        return;
      }

      if (status.status === "error") {
        setToast(status.message || "Sync all could not be completed.");

        if (!cancelled) {
          setIsSyncingAll(false);
          setSyncingId(null);
        }
        return;
      }

      await reloadPlaylists();

      if (!cancelled) {
        setIsSyncingAll(false);
        setSyncingId(null);
      }
    }

    void pollSyncAllStatus().catch((error) => {
      if (!cancelled) {
        setToast(error instanceof Error ? error.message : String(error));
        setIsSyncingAll(false);
        setSyncingId(null);
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
    if (!syncingId || isSyncingAll) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    async function pollSyncStatus() {
      const playlistId = syncingId;
      const status = await getSyncStatus(playlistId);

      if (cancelled) {
        return;
      }

      if (status.status === "syncing") {
        timeoutId = window.setTimeout(pollSyncStatus, SYNC_STATUS_POLL_MS);
        return;
      }

      if (status.status === "completed") {
        await reloadPlaylists();

        if (!cancelled) {
          setSyncingId(null);
        }
        return;
      }

      if (status.status === "error") {
        setToast(status.message || "Sync could not be completed.");

        if (!cancelled) {
          setSyncingId(null);
        }
        return;
      }

      await reloadPlaylists();

      if (!cancelled) {
        setSyncingId(null);
      }
    }

    void pollSyncStatus().catch((error) => {
      if (!cancelled) {
        setToast(error instanceof Error ? error.message : String(error));
        setSyncingId(null);
      }
    });

    return () => {
      cancelled = true;

      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [isSyncingAll, reloadPlaylists, syncingId]);

  async function handleSyncPlaylist(playlistId: string) {
    if (syncingId || isSyncingAll) {
      return;
    }

    setToast("");

    const startResult = await syncPlaylist(playlistId);

    if (!startResult.started) {
      setToast(startResult.message ?? "A sync is already running.");
      await recoverActiveSync(playlists);
      return;
    }

    setIsSyncingAll(false);
    setSyncingId(playlistId);
  }

  async function handleSyncAll() {
    if (syncingId || isSyncingAll || playlists.length === 0) {
      return;
    }

    setToast("");

    const startResult = await syncAllPlaylists();

    if (!startResult.started) {
      setToast(startResult.message ?? "A sync is already running.");
      await recoverActiveSync(playlists);
      return;
    }

    setSyncingId(null);
    setIsSyncingAll(true);
  }

  const syncedCount = playlists.filter((playlist) => playlist.status.type === "synced").length;
  const syncAllDisabled = Boolean(syncingId) || isSyncingAll || playlists.length === 0;

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
          {playlists.map((playlist) => (
            <PlaylistRow
              key={playlist.id}
              playlist={playlist}
              isSyncing={isSyncingAll || syncingId === playlist.id}
              onSync={handleSyncPlaylist}
            />
          ))}
        </div>
      </div>

      {toast ? <Toast message={toast} /> : null}
    </section>
  );
}

export default PlaylistsPage;
