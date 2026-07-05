import { useCallback, useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useLocation, useNavigate } from "react-router-dom";
import { useConfirm } from "../components/ConfirmProvider";
import PlaylistRow from "../components/PlaylistRow";
import { PlaylistRowsSkeleton } from "../components/Skeleton";
import { useToast } from "../components/ToastProvider";
import { useSyncStatus } from "../context/SyncStatusContext";
import PlaylistDetailPage from "./PlaylistDetailPage";
import { USE_MOCK_PLAYLIST_STATUSES, mockPlaylists } from "../data/mockPlaylists";
import {
  PLAYLISTS_UPDATED_EVENT,
  changePlaylistLocation,
  deletePlaylist,
  listMissingPlaylists,
  listPlaylists,
  openFolder,
  openSourceUrl,
  recoverExistingPlaylist,
  resolvePlaylistFolderPath,
  updatePlaylistFolder,
} from "../services/playlistService";
import type { BrokenPlaylist, LongTaskProgress, Platform, PlaylistSummary } from "../services/playlistService";

type PlatformFilter = "all" | Exclude<Platform, "unknown">;

const PLATFORM_FILTERS: Array<{ value: PlatformFilter; label: string }> = [
  { value: "all", label: "All" },
  { value: "youtube", label: "YouTube" },
  { value: "spotify", label: "Spotify" },
  { value: "apple", label: "Apple" },
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
  const location = useLocation();
  const navigate = useNavigate();
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [selectedPlaylistId, setSelectedPlaylistId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [platformFilter, setPlatformFilter] = useState<PlatformFilter>("all");
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [brokenPlaylists, setBrokenPlaylists] = useState<BrokenPlaylist[]>([]);
  const [ignoredRecoveryIds, setIgnoredRecoveryIds] = useState<string[]>([]);
  const { showToast } = useToast();
  const { confirm } = useConfirm();
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
  const setToast = useCallback((message: string, variant: "success" | "error" | "info" = "info") => {
    if (message) {
      showToast(message, variant);
    }
  }, [showToast]);

  const reloadPlaylists = useCallback(async () => {
    if (USE_MOCK_PLAYLIST_STATUSES) {
      setPlaylists(mockPlaylists);
      return mockPlaylists;
    }

    const nextPlaylists = await listPlaylists();
    setPlaylists(nextPlaylists);
    return nextPlaylists;
  }, []);

  const refreshBrokenPlaylists = useCallback(async () => {
    if (USE_MOCK_PLAYLIST_STATUSES) {
      setBrokenPlaylists([]);
      return [];
    }

    const missingPlaylists = await listMissingPlaylists();
    setBrokenPlaylists(missingPlaylists);
    return missingPlaylists;
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialPlaylists() {
      const nextPlaylists = USE_MOCK_PLAYLIST_STATUSES ? mockPlaylists : await listPlaylists();

      if (!cancelled) {
        setPlaylists(nextPlaylists);
        setIsInitialLoading(false);
        void refreshSyncStatuses();
        void refreshBrokenPlaylists();
      }
    }

    function handlePlaylistsUpdated(event: Event) {
      const updatedPlaylists = (event as CustomEvent<PlaylistSummary[]>).detail;

      if (Array.isArray(updatedPlaylists)) {
        setPlaylists(updatedPlaylists);
        void refreshSyncStatuses();
        void refreshBrokenPlaylists();
        return;
      }

      void reloadPlaylists().then(() => {
        void refreshSyncStatuses();
        void refreshBrokenPlaylists();
      });
    }

    void loadInitialPlaylists();
    window.addEventListener(PLAYLISTS_UPDATED_EVENT, handlePlaylistsUpdated);

    return () => {
      cancelled = true;
      window.removeEventListener(PLAYLISTS_UPDATED_EVENT, handlePlaylistsUpdated);
    };
  }, [refreshBrokenPlaylists, refreshSyncStatuses, reloadPlaylists]);

  useEffect(() => {
    const state = location.state as { selectedPlaylistId?: string } | null;

    if (!state?.selectedPlaylistId) {
      return;
    }

    setSelectedPlaylistId(state.selectedPlaylistId);
    navigate("/playlists", { replace: true, state: null });
  }, [location.state, navigate]);

  useEffect(() => {
    void reloadPlaylists();
    void refreshBrokenPlaylists();
  }, [refreshBrokenPlaylists, reloadPlaylists, statusVersion]);

  async function handleSyncPlaylist(playlistId: string) {
    if (isSyncingAll || isActiveProgress(getPlaylistProgress(playlistId))) {
      return;
    }

    setToast("");

    if (USE_MOCK_PLAYLIST_STATUSES) {
      setToast("Mock status mode is enabled.", "info");
      return;
    }

    const result = await syncPlaylist(playlistId);

    if (!result.started) {
      setToast(result.message ?? "A sync is already running.", "error");
      await refreshSyncStatuses();
    }
  }

  async function handleDownloadMissing(playlistId: string) {
    if (isSyncingAll || isActiveProgress(getPlaylistProgress(playlistId))) {
      return;
    }

    setToast("");

    if (USE_MOCK_PLAYLIST_STATUSES) {
      setToast("Mock status mode is enabled.", "info");
      return;
    }

    const result = await downloadMissing(playlistId);

    if (!result.started) {
      setToast(result.message ?? "A sync or download is already running.", "error");
      await refreshSyncStatuses();
    }
  }

  async function handleCancelPlaylistSync(playlistId: string) {
    if (!isActiveProgress(getPlaylistProgress(playlistId))) {
      return;
    }

    const result = await cancelPlaylistSync(playlistId);

    if (!result.ok) {
      setToast(result.message, "error");
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
      setToast("Folder could not be opened.", "error");
    }
  }

  async function handleOpenPlaylistSource(playlistId: string) {
    const playlist = playlists.find((item) => item.id === playlistId);
    const sourceUrl = playlist?.sourceUrl;

    if (!sourceUrl) {
      setToast("Source link is unavailable.", "error");
      return;
    }

    const opened = await openSourceUrl(sourceUrl);
    if (!opened) {
      setToast("Source could not be opened.", "error");
    }
  }

  async function handleChangePlaylistLocation(playlistId: string) {
    if (isActiveProgress(getPlaylistProgress(playlistId))) {
      setToast("Cannot change location while this playlist is syncing.", "error");
      return;
    }

    let selectedFolder: string | string[] | null;

    try {
      selectedFolder = await open({
        directory: true,
        multiple: false,
        title: "Change playlist location",
      });
    } catch {
      setToast("Folder picker could not be opened.", "error");
      return;
    }

    const folder = Array.isArray(selectedFolder) ? selectedFolder[0] : selectedFolder;

    if (!folder) {
      return;
    }

    setToast("Changing playlist location...", "info");

    if (USE_MOCK_PLAYLIST_STATUSES) {
      setToast("Mock status mode is enabled.", "info");
      return;
    }

    const result = await changePlaylistLocation(playlistId, folder);

    if (!result.ok) {
      setToast(result.message, "error");
      await refreshSyncStatuses();
      return;
    }

    await reloadPlaylists();
    await refreshBrokenPlaylists();
    await refreshSyncStatuses();
    setToast(result.message, "success");
  }

  async function handleRemovePlaylist(playlistId: string) {
    if (isSyncingAll || hasActiveIndividualSyncs) {
      setToast("Cannot remove playlist while a sync or download is running.", "error");
      return;
    }

    const confirmed = await confirm({
      title: "Remove playlist?",
      message: "This will remove the playlist from YouSync. Local audio files will not be deleted.",
      confirmLabel: "Remove",
      cancelLabel: "Cancel",
      danger: true,
    });

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
      setToast(result.message, "error");
      await refreshSyncStatuses();
      return;
    }

    await reloadPlaylists();
    setToast(result.message, "success");
  }

  async function handleRemovePlaylistWithLocalFiles(playlistId: string) {
    if (isSyncingAll || hasActiveIndividualSyncs) {
      setToast("Cannot remove playlist while a sync or download is running.", "error");
      return;
    }

    const playlist = playlists.find((item) => item.id === playlistId);

    if (!playlist) {
      return;
    }

    const confirmed = await confirm({
      title: "Remove playlist and local files?",
      message: `Remove "${playlist.title}" from YouSync and delete its local audio files? This cannot be undone.`,
      confirmLabel: "Remove",
      cancelLabel: "Cancel",
      danger: true,
    });

    if (!confirmed) {
      return;
    }

    setToast("Removing playlist and local files...", "info");

    if (USE_MOCK_PLAYLIST_STATUSES) {
      setPlaylists((currentPlaylists) => currentPlaylists.filter((playlist) => playlist.id !== playlistId));
      return;
    }

    const result = await deletePlaylist(playlistId, true);

    if (!result.ok) {
      setToast(result.message, "error");
      await refreshSyncStatuses();
      return;
    }

    await reloadPlaylists();
    await refreshBrokenPlaylists();
    await refreshSyncStatuses();
    setToast(result.message, "success");
  }

  async function handleRecoverExistingPlaylist() {
    if (isSyncingAll || hasActiveIndividualSyncs) {
      setToast("Cannot recover a playlist while a sync or download is running.", "error");
      return;
    }

    if (USE_MOCK_PLAYLIST_STATUSES) {
      setToast("Mock status mode is enabled.", "info");
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
      setToast("Folder picker could not be opened.", "error");
      return;
    }

    const folder = Array.isArray(selectedFolder) ? selectedFolder[0] : selectedFolder;

    if (!folder) {
      return;
    }

    setToast("Recovering existing playlist...", "info");

    const result = await recoverExistingPlaylist(folder);

    if (!result.ok) {
      setToast(result.message, "error");
      await refreshSyncStatuses();
      return;
    }

    await reloadPlaylists();
    await refreshBrokenPlaylists();
    await refreshSyncStatuses();
    setToast(result.message, "success");
  }

  async function handleLocateBrokenPlaylist(playlistId: string) {
    if (isSyncingAll || hasActiveIndividualSyncs) {
      setToast("Cannot recover a playlist while a sync or download is running.", "error");
      return;
    }

    let selectedFolder: string | string[] | null;

    try {
      selectedFolder = await open({
        directory: true,
        multiple: false,
        title: "Find playlist folder",
      });
    } catch {
      setToast("Folder picker could not be opened.", "error");
      return;
    }

    const folder = Array.isArray(selectedFolder) ? selectedFolder[0] : selectedFolder;

    if (!folder) {
      return;
    }

    setToast("Recovering playlist folder...", "info");

    const result = await updatePlaylistFolder(playlistId, folder);

    if (!result.ok) {
      setToast(result.message, "error");
      await refreshBrokenPlaylists();
      return;
    }

    setIgnoredRecoveryIds((current) => current.filter((id) => !result.updatedPlaylistIds?.includes(id)));
    await reloadPlaylists();
    await refreshBrokenPlaylists();
    await refreshSyncStatuses();
    setToast(result.message, "success");
  }

  async function handleRemoveBrokenPlaylist(playlistId: string) {
    if (isSyncingAll || hasActiveIndividualSyncs) {
      setToast("Cannot remove playlist while a sync or download is running.", "error");
      return;
    }

    const confirmed = await confirm({
      title: "Remove playlist?",
      message: "This will remove the playlist from YouSync. Local audio files will not be deleted.",
      confirmLabel: "Remove",
      cancelLabel: "Cancel",
      danger: true,
    });

    if (!confirmed) {
      return;
    }

    const result = await deletePlaylist(playlistId);

    if (!result.ok) {
      setToast(result.message, "error");
      await refreshBrokenPlaylists();
      return;
    }

    setBrokenPlaylists((current) => current.filter((playlist) => playlist.id !== playlistId));
    setIgnoredRecoveryIds((current) => current.filter((id) => id !== playlistId));
    await reloadPlaylists();
    await refreshSyncStatuses();
    setToast(result.message, "success");
  }

  function handleIgnoreBrokenPlaylist(playlistId: string) {
    setIgnoredRecoveryIds((current) => (current.includes(playlistId) ? current : [...current, playlistId]));
  }

  async function handleSyncAll() {
    if (hasActiveIndividualSyncs || isSyncingAll || playlists.length === 0) {
      return;
    }

    setToast("");

    if (USE_MOCK_PLAYLIST_STATUSES) {
      setToast("Mock status mode is enabled.", "info");
      return;
    }

    const result = await syncAll();

    if (!result.started) {
      setToast(result.message ?? "A sync is already running.", "error");
      await refreshSyncStatuses();
    }
  }

  async function handleCancelSyncAll() {
    if (!isSyncingAll) {
      return;
    }

    const result = await cancelSyncAll();

    if (!result.ok) {
      setToast(result.message, "error");
      return;
    }

    await reloadPlaylists();
  }

  const syncedCount = playlists.filter((playlist) => playlist.status.type === "synced").length;
  const syncAllDisabled = hasActiveIndividualSyncs || isSyncingAll || playlists.length === 0;
  const recoverDisabled = hasActiveIndividualSyncs || isSyncingAll;
  const recoveryActionsDisabled = hasActiveIndividualSyncs || isSyncingAll;
  const visibleBrokenPlaylists = brokenPlaylists.filter((playlist) => !ignoredRecoveryIds.includes(playlist.id));
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
          {isInitialLoading ? <PlaylistRowsSkeleton /> : null}
          {!isInitialLoading ? filteredPlaylists.map((playlist) => {
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
                onChangeLocation={handleChangePlaylistLocation}
                onRemove={handleRemovePlaylist}
                onRemoveWithLocalFiles={handleRemovePlaylistWithLocalFiles}
              />
            );
          }) : null}
          {!isInitialLoading && filteredPlaylists.length === 0 ? (
            <div className="playlist-empty-filter">No playlist matches your filters.</div>
          ) : null}
        </div>
      </div>

      {visibleBrokenPlaylists.length > 0 ? (
        <div className="recovery-modal-backdrop" role="presentation">
          <div className="recovery-modal" role="dialog" aria-modal="true" aria-labelledby="recovery-modal-title">
            <div className="recovery-modal-header">
              <div>
                <p className="eyebrow">Recovery mode</p>
                <h2 id="recovery-modal-title">Playlist folders not found</h2>
              </div>
              <button
                className="recovery-modal-close"
                type="button"
                aria-label="Ignore all broken playlists for now"
                onClick={() => setIgnoredRecoveryIds(visibleBrokenPlaylists.map((playlist) => playlist.id))}
              >
                ×
              </button>
            </div>

            <p className="recovery-modal-description">
              YouSync found playlists whose local folder no longer exists. Find the new folder, remove the playlist from YouSync, or ignore it for this launch.
            </p>

            <div className="recovery-playlist-list">
              {visibleBrokenPlaylists.map((playlist) => (
                <article className="recovery-playlist-card" key={playlist.id}>
                  <div className="recovery-playlist-info">
                    <strong>{playlist.title}</strong>
                    <span>{playlist.platform}</span>
                    <code>{playlist.missingPath || resolvePlaylistFolderPath(playlist.path)}</code>
                  </div>

                  <div className="recovery-playlist-actions">
                    <button
                      type="button"
                      disabled={recoveryActionsDisabled}
                      onClick={() => void handleLocateBrokenPlaylist(playlist.id)}
                    >
                      Find folder
                    </button>
                    <button
                      type="button"
                      disabled={recoveryActionsDisabled}
                      onClick={() => handleIgnoreBrokenPlaylist(playlist.id)}
                    >
                      Ignore
                    </button>
                    <button
                      className="danger"
                      type="button"
                      disabled={recoveryActionsDisabled}
                      onClick={() => void handleRemoveBrokenPlaylist(playlist.id)}
                    >
                      Remove
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export default PlaylistsPage;
