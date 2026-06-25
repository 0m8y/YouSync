import { useCallback, useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import PlaylistRow from "../components/PlaylistRow";
import Toast from "../components/Toast";
import { useSyncStatus } from "../context/SyncStatusContext";
import PlaylistDetailPage from "./PlaylistDetailPage";
import { USE_MOCK_PLAYLIST_STATUSES, mockPlaylists } from "../data/mockPlaylists";
import {
  PLAYLISTS_UPDATED_EVENT,
  deletePlaylist,
  listPlaylists,
  openFolder,
  openSourceUrl,
  recoverExistingPlaylist,
  resolvePlaylistFolderPath,
} from "../services/playlistService";
import type { LongTaskProgress, Platform, PlaylistSummary } from "../services/playlistService";

type PlatformFilter = "all" | Exclude<Platform, "unknown">;

const PLATFORM_FILTERS: Array<{ value: PlatformFilter; label: string }> = [
  { value: "all", label: "All" },
  { value: "youtube", label: "YouTube" },
  { value: "spotify", label: "Spotify" },
  { value: "apple", label: "Apple" },
  { value: "soundcloud", label: "SoundCloud" },
];

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

function PlaylistsPage() {
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [selectedPlaylistId, setSelectedPlaylistId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [platformFilter, setPlatformFilter] = useState<PlatformFilter>("all");
  const [toast, setToast] = useState("");
  const {
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
  } = useSyncStatus();

  const reloadPlaylists = useCallback(async () => {
    if (USE_MOCK_PLAYLIST_STATUSES) {
      setPlaylists(mockPlaylists);
      return mockPlaylists;
    }

    const nextPlaylists = await listPlaylists();
    setPlaylists(nextPlaylists);
    return nextPlaylists;
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialPlaylists() {
      const nextPlaylists = USE_MOCK_PLAYLIST_STATUSES ? mockPlaylists : await listPlaylists();

      if (!cancelled) {
        setPlaylists(nextPlaylists);
        void refreshSyncStatuses();
      }
    }

    function handlePlaylistsUpdated(event: Event) {
      const updatedPlaylists = (event as CustomEvent<PlaylistSummary[]>).detail;

      if (Array.isArray(updatedPlaylists)) {
        setPlaylists(updatedPlaylists);
        void refreshSyncStatuses();
        return;
      }

      void reloadPlaylists().then(() => refreshSyncStatuses());
    }

    void loadInitialPlaylists();
    window.addEventListener(PLAYLISTS_UPDATED_EVENT, handlePlaylistsUpdated);

    return () => {
      cancelled = true;
      window.removeEventListener(PLAYLISTS_UPDATED_EVENT, handlePlaylistsUpdated);
    };
  }, [refreshSyncStatuses, reloadPlaylists]);

  useEffect(() => {
    void reloadPlaylists();
  }, [reloadPlaylists, statusVersion]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timeout = window.setTimeout(() => setToast(""), 3200);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  async function handleSyncPlaylist(playlistId: string) {
    if (isSyncingAll || isActiveProgress(getPlaylistProgress(playlistId))) {
      return;
    }

    setToast("");

    if (USE_MOCK_PLAYLIST_STATUSES) {
      setToast("Mock status mode is enabled.");
      return;
    }

    const result = await syncPlaylist(playlistId);

    if (!result.started) {
      setToast(result.message ?? "A sync is already running.");
      await refreshSyncStatuses();
    }
  }

  async function handleDownloadMissing(playlistId: string) {
    if (isSyncingAll || isActiveProgress(getPlaylistProgress(playlistId))) {
      return;
    }

    setToast("");

    if (USE_MOCK_PLAYLIST_STATUSES) {
      setToast("Mock status mode is enabled.");
      return;
    }

    const result = await downloadMissing(playlistId);

    if (!result.started) {
      setToast(result.message ?? "A sync or download is already running.");
      await refreshSyncStatuses();
    }
  }

  async function handleCancelPlaylistSync(playlistId: string) {
    if (!isActiveProgress(getPlaylistProgress(playlistId))) {
      return;
    }

    const result = await cancelPlaylistSync(playlistId);

    if (!result.ok) {
      setToast(result.message);
      return;
    }

    await reloadPlaylists();
  }

  async function handleOpenPlaylistFolder(playlistId: string) {
    const playlist = playlists.find((item) => item.id === playlistId);

    if (!playlist) {
      return;
    }

    const opened = await openFolder(resolvePlaylistFolderPath(playlist.path));
    if (!opened) {
      setToast("Folder could not be opened.");
    }
  }

  async function handleOpenPlaylistSource(playlistId: string) {
    const playlist = playlists.find((item) => item.id === playlistId);
    const sourceUrl = playlist?.sourceUrl;

    if (!sourceUrl) {
      setToast("Source link is unavailable.");
      return;
    }

    const opened = await openSourceUrl(sourceUrl);
    if (!opened) {
      setToast("Source could not be opened.");
    }
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
      await refreshSyncStatuses();
      return;
    }

    await reloadPlaylists();
    setToast(result.message);
  }

  async function handleRecoverExistingPlaylist() {
    if (isSyncingAll || hasActiveIndividualSyncs) {
      setToast("Cannot recover a playlist while a sync or download is running.");
      return;
    }

    if (USE_MOCK_PLAYLIST_STATUSES) {
      setToast("Mock status mode is enabled.");
      return;
    }

    let selectedFolder: string | string[] | null;

    try {
      selectedFolder = await open({
        directory: true,
        multiple: false,
        title: "Recover existing YouSync playlist",
      });
    } catch {
      setToast("Folder picker could not be opened.");
      return;
    }

    const folder = Array.isArray(selectedFolder) ? selectedFolder[0] : selectedFolder;

    if (!folder) {
      return;
    }

    setToast("Recovering existing playlist...");

    const result = await recoverExistingPlaylist(folder);

    if (!result.ok) {
      setToast(result.message);
      await refreshSyncStatuses();
      return;
    }

    await reloadPlaylists();
    await refreshSyncStatuses();
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

    const result = await syncAll();

    if (!result.started) {
      setToast(result.message ?? "A sync is already running.");
      await refreshSyncStatuses();
    }
  }

  async function handleCancelSyncAll() {
    if (!isSyncingAll) {
      return;
    }

    const result = await cancelSyncAll();

    if (!result.ok) {
      setToast(result.message);
      return;
    }

    await reloadPlaylists();
  }

  const syncedCount = playlists.filter((playlist) => playlist.status.type === "synced").length;
  const syncAllDisabled = hasActiveIndividualSyncs || isSyncingAll || playlists.length === 0;
  const recoverDisabled = hasActiveIndividualSyncs || isSyncingAll;
  const normalizedSearch = searchQuery.trim().toLowerCase();
  const filteredPlaylists = playlists.filter((playlist) => {
    const matchesPlatform = platformFilter === "all" || playlist.platform === platformFilter;
    const matchesSearch = !normalizedSearch || playlist.title.toLowerCase().includes(normalizedSearch);
    return matchesPlatform && matchesSearch;
  });

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
          {isSyncingAll ? (
            <button
              className="topbar-stop-btn"
              type="button"
              title="Stop sync all"
              aria-label="Stop sync all"
              onClick={handleCancelSyncAll}
            >
              ⏹
            </button>
          ) : null}
          <button type="button" disabled={recoverDisabled} onClick={handleRecoverExistingPlaylist}>
            Recover playlist
          </button>
        </div>

        {syncAllProgress ? (
          <div className="topbar-progress" role="status">
            {isSyncingAll ? <span className="sync-spinner" aria-hidden="true" /> : null}
            <span>{progressLabel(syncAllProgress)}</span>
          </div>
        ) : null}
      </header>

      <div className="playlists-content">
        <div className="playlist-filters" aria-label="Playlist filters">
          <input
            type="search"
            value={searchQuery}
            placeholder="Search playlists..."
            aria-label="Search playlists"
            onChange={(event) => setSearchQuery(event.target.value)}
          />
          <div className="platform-filters" role="group" aria-label="Filter by platform">
            {PLATFORM_FILTERS.map((filter) => (
              <button
                key={filter.value}
                className={platformFilter === filter.value ? "active" : ""}
                type="button"
                aria-pressed={platformFilter === filter.value}
                onClick={() => setPlatformFilter(filter.value)}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>

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
          {filteredPlaylists.map((playlist) => {
            const rowProgress = getPlaylistProgress(playlist.id);

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
                onOpenFolder={handleOpenPlaylistFolder}
                onOpenSource={handleOpenPlaylistSource}
                onRemove={handleRemovePlaylist}
              />
            );
          })}
          {filteredPlaylists.length === 0 ? (
            <div className="playlist-empty-filter">No playlist matches your filters.</div>
          ) : null}
        </div>
      </div>

      {toast ? <Toast message={toast} /> : null}
    </section>
  );
}

export default PlaylistsPage;
