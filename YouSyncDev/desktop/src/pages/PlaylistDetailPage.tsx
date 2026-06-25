import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { convertFileSrc } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { useConfirm } from "../components/ConfirmProvider";
import { useToast } from "../components/ToastProvider";
import { useSyncStatus } from "../context/SyncStatusContext";
import { getPlatform } from "../data/mockData";
import { USE_MOCK_PLAYLIST_STATUSES, getMockPlaylistDetail } from "../data/mockPlaylists";
import {
  PLAYLISTS_UPDATED_EVENT,
  changePlaylistLocation,
  deletePlaylist,
  getPlaylistDetails,
  openFolder,
  openLocalFile,
  openSourceUrl,
  redownloadTrack,
} from "../services/playlistService";
import type { LongTaskProgress, PlaylistDetail, PlaylistTrack } from "../services/playlistService";

type PlaylistDetailPageProps = {
  playlistId: string;
  onBack: () => void;
};

type TrackStatusFilter = "All" | "Synced" | "Missing" | "Downloaded" | "Metadata" | "Error";

const TRACK_STATUS_FILTERS: TrackStatusFilter[] = ["All", "Synced", "Missing", "Downloaded", "Metadata", "Error"];

function normalizeTrackStatus(status: string): TrackStatusFilter {
  const normalized = status.trim().toLowerCase();

  if (normalized === "synced") {
    return "Synced";
  }

  if (normalized === "downloaded") {
    return "Downloaded";
  }

  if (normalized === "metadata") {
    return "Metadata";
  }

  if (normalized === "error") {
    return "Error";
  }

  return "Missing";
}

function statusClass(status: string) {
  return normalizeTrackStatus(status).toLowerCase();
}

function progressLabel(progress: LongTaskProgress | null) {
  if (!progress) {
    return "";
  }

  const parts = [];
  parts.push(progress.message || (progress.phase === "downloading" ? "Downloading..." : "Syncing..."));

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

function trackSourceUrl(track: PlaylistTrack) {
  return track.sourceUrl || track.url || "";
}

function canOpenTrackLocalFile(track: PlaylistTrack) {
  return Boolean(track.localPath && track.isDownloaded);
}

function PlaylistDetailPage({ playlistId, onBack }: PlaylistDetailPageProps) {
  const [detail, setDetail] = useState<PlaylistDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const [trackMenuOpen, setTrackMenuOpen] = useState<number | null>(null);
  const [coverFailed, setCoverFailed] = useState(false);
  const [trackSearch, setTrackSearch] = useState("");
  const [trackStatusFilter, setTrackStatusFilter] = useState<TrackStatusFilter>("All");
  const liveDetailRefreshInFlightRef = useRef(false);
  const liveDetailRefreshPendingRef = useRef(false);
  const lastLiveDetailProgressKeyRef = useRef("");
  const { showToast } = useToast();
  const { confirm } = useConfirm();
  const {
    statusVersion,
    isActiveProgress,
    getPlaylistProgress,
    syncPlaylist,
    downloadMissing,
    cancelPlaylistSync,
    refreshSyncStatuses,
  } = useSyncStatus();
  const syncProgress = getPlaylistProgress(playlistId);
  const isSyncing = isActiveProgress(syncProgress);
  const showProgress = Boolean(syncProgress && (isSyncing || syncProgress.status === "cancelled"));
  const setToast = useCallback((message: string, variant: "success" | "error" | "info" = "info") => {
    if (message) {
      showToast(message, variant);
    }
  }, [showToast]);

  async function loadDetail(showSkeleton = false) {
    if (showSkeleton || !detail) {
      setIsLoading(true);
    }

    if (USE_MOCK_PLAYLIST_STATUSES) {
      const nextDetail = getMockPlaylistDetail(playlistId);
      setDetail(nextDetail);
      setIsLoading(false);
      return nextDetail;
    }

    const nextDetail = await getPlaylistDetails(playlistId);
    setDetail(nextDetail);
    setIsLoading(false);
    return nextDetail;
  }

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);

    async function load() {
      const nextDetail = USE_MOCK_PLAYLIST_STATUSES
        ? getMockPlaylistDetail(playlistId)
        : await getPlaylistDetails(playlistId);

      if (!cancelled) {
        setDetail(nextDetail);
        setIsLoading(false);
        setCoverFailed(false);
        setTrackMenuOpen(null);
        setTrackSearch("");
        setTrackStatusFilter("All");
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [playlistId]);

  useEffect(() => {
    if (statusVersion > 0) {
      void loadDetail(false);
    }
  }, [statusVersion]);

  useEffect(() => {
    const status = syncProgress?.status ?? "";
    const phase = syncProgress?.phase ?? "";
    const isTerminal = status === "completed" || status === "cancelled" || status === "error";

    if (!isSyncing && !isTerminal) {
      lastLiveDetailProgressKeyRef.current = "";
      return;
    }

    const progressKey = [
      playlistId,
      status,
      phase,
      syncProgress?.current ?? "",
      syncProgress?.total ?? "",
      syncProgress?.failedCount ?? "",
      syncProgress?.message ?? "",
      syncProgress?.currentTrack ?? "",
    ].join("|");

    if (lastLiveDetailProgressKeyRef.current === progressKey) {
      return;
    }

    lastLiveDetailProgressKeyRef.current = progressKey;

    if (liveDetailRefreshInFlightRef.current) {
      liveDetailRefreshPendingRef.current = true;
      return;
    }

    liveDetailRefreshInFlightRef.current = true;

    function refreshLiveDetail() {
      void loadDetail(false).finally(() => {
        if (liveDetailRefreshPendingRef.current) {
          liveDetailRefreshPendingRef.current = false;
          refreshLiveDetail();
          return;
        }

        liveDetailRefreshInFlightRef.current = false;
      });
    }

    refreshLiveDetail();
  }, [
    isSyncing,
    playlistId,
    syncProgress?.status,
    syncProgress?.phase,
    syncProgress?.current,
    syncProgress?.total,
    syncProgress?.failedCount,
    syncProgress?.message,
    syncProgress?.currentTrack,
  ]);

  useEffect(() => {
    if (!menuOpen && trackMenuOpen === null) {
      return;
    }

    function closeMenus() {
      setMenuOpen(false);
      setTrackMenuOpen(null);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeMenus();
      }
    }

    document.addEventListener("mousedown", closeMenus);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", closeMenus);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuOpen, trackMenuOpen]);

  const playlist = detail?.playlist ?? null;
  const platform = playlist ? getPlatform(playlist.platform) : null;
  const coverSrc = useMemo(
    () => (playlist?.coverPath ? convertFileSrc(playlist.coverPath) : null),
    [playlist?.coverPath]
  );
  const showCover = Boolean(coverSrc && !coverFailed);
  const trackStatusCounts = useMemo(() => {
    const counts: Record<TrackStatusFilter, number> = {
      All: detail?.tracks.length ?? 0,
      Synced: 0,
      Missing: 0,
      Downloaded: 0,
      Metadata: 0,
      Error: 0,
    };

    for (const track of detail?.tracks ?? []) {
      counts[normalizeTrackStatus(track.status)] += 1;
    }

    return counts;
  }, [detail?.tracks]);

  const visibleTrackStatusFilters = useMemo(
    () => TRACK_STATUS_FILTERS.filter((filter) => filter === "All" || trackStatusCounts[filter] > 0),
    [trackStatusCounts]
  );

  useEffect(() => {
    if (trackStatusFilter !== "All" && trackStatusCounts[trackStatusFilter] === 0) {
      setTrackStatusFilter("All");
    }
  }, [trackStatusCounts, trackStatusFilter]);

  const filteredTracks = useMemo(() => {
    const query = trackSearch.trim().toLowerCase();

    return (detail?.tracks ?? []).filter((track) => {
      const status = normalizeTrackStatus(track.status);

      if (trackStatusFilter !== "All" && status !== trackStatusFilter) {
        return false;
      }

      if (!query) {
        return true;
      }

      return [
        track.title,
        track.artist,
        track.status,
        trackSourceUrl(track),
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query));
    });
  }, [detail?.tracks, trackSearch, trackStatusFilter]);


  async function handleSyncNow() {
    if (isSyncing) {
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
    }
  }

  async function handleDownloadMissing() {
    setMenuOpen(false);

    if (isSyncing) {
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
    }
  }

  async function handleCancelSync() {
    if (!isSyncing) {
      return;
    }

    const result = await cancelPlaylistSync(playlistId);

    if (!result.ok) {
      setToast(result.message, "error");
      return;
    }

    await loadDetail(false);
  }

  async function handleRemovePlaylist() {
    setMenuOpen(false);

    if (isSyncing) {
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
      onBack();
      return;
    }

    const result = await deletePlaylist(playlistId);

    if (!result.ok) {
      setToast(result.message, "error");
      return;
    }

    setToast(result.message, "success");
    onBack();
  }

  async function handleRemovePlaylistWithLocalFiles() {
    setMenuOpen(false);

    if (isSyncing) {
      setToast("Cannot remove playlist while a sync or download is running.", "error");
      return;
    }

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
      onBack();
      return;
    }

    const result = await deletePlaylist(playlistId, true);

    if (!result.ok) {
      setToast(result.message, "error");
      return;
    }

    setToast(result.message, "success");
    onBack();
  }

  async function handleOpenFolder() {
    if (!playlist) {
      return;
    }

    const opened = await openFolder(playlist.path);
    if (!opened) {
      setToast("Folder could not be opened.", "error");
    }
  }

  async function handleOpenSource() {
    if (!playlist?.sourceUrl) {
      return;
    }

    const opened = await openSourceUrl(playlist.sourceUrl);
    if (!opened) {
      setToast("Source could not be opened.", "error");
    }
  }

  async function handleChangePlaylistLocation() {
    setMenuOpen(false);

    if (isSyncing) {
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
      return;
    }

    await loadDetail(false);
    window.dispatchEvent(new CustomEvent(PLAYLISTS_UPDATED_EVENT));
    setToast(result.message, "success");
  }

  async function handlePlayTrack(track: PlaylistTrack) {
    if (!canOpenTrackLocalFile(track)) {
      return;
    }

    await openLocalFile(track.localPath ?? "");
  }

  async function handleOpenTrackSource(track: PlaylistTrack) {
    const sourceUrl = trackSourceUrl(track);

    if (!sourceUrl) {
      return;
    }

    await openSourceUrl(sourceUrl);
  }

  async function handleOpenTrackLocalFile(track: PlaylistTrack) {
    if (!canOpenTrackLocalFile(track)) {
      return;
    }

    await openLocalFile(track.localPath ?? "");
  }

  async function handleRedownloadTrack(track: PlaylistTrack) {
    setTrackMenuOpen(null);

    if (isSyncing) {
      return;
    }

    setToast("");

    if (USE_MOCK_PLAYLIST_STATUSES) {
      setToast("Mock status mode is enabled.", "info");
      return;
    }

    const result = await redownloadTrack(playlistId, track.index);

    if (!result.ok) {
      setToast(result.message ?? "Track could not be redownloaded.", "error");
      return;
    }

    setToast(result.message ?? "Track redownload started.", "info");
    await refreshSyncStatuses();
  }

  if (isLoading || !playlist || !detail) {
    return (
      <section className="playlist-detail-page" aria-labelledby="playlist-detail-title">
        <header className="detail-topbar">
          <button className="detail-btn" type="button" onClick={onBack}>
            <span aria-hidden="true">←</span>
            <span>Playlists</span>
          </button>
          <span className="detail-sep" />
          <span className="detail-topbar-title">Loading...</span>
        </header>
      </section>
    );
  }

  return (
    <section className="playlist-detail-page" aria-labelledby="playlist-detail-title">
      <header className="detail-topbar">
        <button className="detail-btn" type="button" onClick={onBack}>
          <span aria-hidden="true">←</span>
          <span>Playlists</span>
        </button>
        <span className="detail-sep" />
        <span className="detail-topbar-title">{playlist.title}</span>
      </header>

      <div className="detail-header">
        <div className="detail-header-inner">
          <div className={`detail-cover ${playlist.platform}`} aria-hidden="true">
            {showCover ? (
              <img
                src={coverSrc ?? ""}
                alt=""
                onError={() => setCoverFailed(true)}
              />
            ) : (
              "♪"
            )}
          </div>

          <div className="detail-info">
            <h1 id="playlist-detail-title">{playlist.title}</h1>
            <div className="detail-meta-row">
              <span
                className="detail-platform-badge"
                style={{ "--platform-accent": platform?.accent } as CSSProperties}
              >
                <span />
                {platform?.label}
              </span>
              <span className="detail-sep" />
              <span>{playlist.tracks} tracks</span>
              <span className="detail-sep" />
              <span className={`detail-status ${playlist.status.type}`}>
                <span />
                {playlist.status.label}
              </span>
              <span className="detail-sep" />
              <span>Last synced {playlist.lastSynced || "—"}</span>
              <span className="detail-sep" />
              <span aria-hidden="true">□</span>
              <span className="detail-folder-path">{playlist.path}</span>
            </div>
          </div>

          <div className="detail-actions">
            {isSyncing ? (
              <button
                className="detail-stop-btn"
                type="button"
                title="Stop sync"
                aria-label="Stop sync"
                onClick={handleCancelSync}
              >
                ⏹
              </button>
            ) : null}
            <button
              className="detail-btn-primary"
              type="button"
              disabled={isSyncing}
              onClick={handleSyncNow}
            >
              <span aria-hidden="true">{isSyncing ? "◌" : "↻"}</span>
              <span>{isSyncing ? "Syncing..." : "Sync now"}</span>
            </button>
            <button className="detail-btn" type="button" onClick={handleOpenFolder}>
              <span aria-hidden="true">□</span>
              <span>Open folder</span>
            </button>
            <button className="detail-btn" type="button" onClick={handleOpenSource}>
              <span aria-hidden="true">↗</span>
              <span>Source</span>
            </button>
            <div
              className="detail-menu-wrap"
              onMouseDown={(event) => event.stopPropagation()}
            >
              <button
                className="detail-btn detail-dots"
                type="button"
                aria-label="More actions"
                aria-expanded={menuOpen}
                onClick={() => {
                  setTrackMenuOpen(null);
                  setMenuOpen((open) => !open);
                }}
              >
                ⋮
              </button>
              {menuOpen ? (
                <div className="detail-menu" role="menu">
                  <button
                    type="button"
                    role="menuitem"
                    disabled={isSyncing}
                    onClick={handleDownloadMissing}
                  >
                    Download missing
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    disabled={isSyncing}
                    onClick={handleChangePlaylistLocation}
                  >
                    Change playlist location
                  </button>
                  <div className="menu-separator" role="separator" />
                  <button
                    className="menu-danger"
                    type="button"
                    role="menuitem"
                    disabled={isSyncing}
                    onClick={handleRemovePlaylist}
                  >
                    Remove playlist
                  </button>
                  <button
                    className="menu-danger menu-danger-strong"
                    type="button"
                    role="menuitem"
                    disabled={isSyncing}
                    onClick={handleRemovePlaylistWithLocalFiles}
                  >
                    Remove playlist + local files
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      {showProgress && syncProgress ? (
        <div className="detail-progress" role="status">
          {isSyncing ? <span className="sync-spinner" aria-hidden="true" /> : null}
          <span>{progressLabel(syncProgress)}</span>
        </div>
      ) : null}

      <div className="detail-track-tools">
        <label className="detail-track-search" htmlFor="track-search-input">
          <span>Search tracks</span>
          <input
            id="track-search-input"
            type="search"
            value={trackSearch}
            placeholder="Search by title or artist..."
            onChange={(event) => {
              setTrackSearch(event.target.value);
              setTrackMenuOpen(null);
            }}
          />
        </label>
        <div className="detail-status-filters" aria-label="Filter tracks by status">
          {visibleTrackStatusFilters.map((filter) => (
            <button
              className={trackStatusFilter === filter ? "active" : ""}
              key={filter}
              type="button"
              aria-pressed={trackStatusFilter === filter}
              onClick={() => {
                setTrackStatusFilter(filter);
                setTrackMenuOpen(null);
              }}
            >
              <span>{filter}</span>
              <strong>{trackStatusCounts[filter]}</strong>
            </button>
          ))}
        </div>
      </div>

      <div className="detail-track-result-count" aria-live="polite">
        {filteredTracks.length === detail.tracks.length
          ? `${detail.tracks.length} tracks`
          : `${filteredTracks.length} / ${detail.tracks.length} tracks`}
      </div>

      <div className="detail-track-header" aria-hidden="true">
        <span>#</span>
        <span>Title</span>
        <span>Artist</span>
        <span>Status</span>
        <span />
      </div>

      <div className="detail-track-table">
        {filteredTracks.length > 0 ? filteredTracks.map((track) => {
          const sourceUrl = trackSourceUrl(track);
          const canOpenLocal = canOpenTrackLocalFile(track);
          const isTrackMenuOpen = trackMenuOpen === track.index;

          return (
            <div
              className="detail-track-row"
              key={`${track.index}-${track.title}`}
            >
              <span className="detail-track-num">{track.index}</span>
              <span className="detail-track-title">{track.title}</span>
              <span className="detail-track-artist">{track.artist || "—"}</span>
              <span className={`detail-track-status ${statusClass(track.status)}`}>
                <span />
                {track.status}
              </span>
              <span
                className="detail-track-actions"
                onClick={(event) => event.stopPropagation()}
                onMouseDown={(event) => event.stopPropagation()}
              >
                <button
                  className="track-play-btn"
                  type="button"
                  disabled={!canOpenLocal}
                  onClick={() => handlePlayTrack(track)}
                >
                  Play
                </button>
                <span className="track-menu-wrap">
                  <button
                    className="track-more-btn"
                    type="button"
                    aria-label={`More actions for ${track.title}`}
                    aria-expanded={isTrackMenuOpen}
                    onClick={() => {
                      setMenuOpen(false);
                      setTrackMenuOpen((current) => (current === track.index ? null : track.index));
                    }}
                  >
                    ⋮
                  </button>
                  {isTrackMenuOpen ? (
                    <span className="detail-menu track-menu" role="menu">
                      <button
                        type="button"
                        role="menuitem"
                        disabled={isSyncing}
                        onClick={() => handleRedownloadTrack(track)}
                      >
                        Redownload track
                      </button>
                      <button
                        type="button"
                        role="menuitem"
                        disabled={!sourceUrl}
                        onClick={() => {
                          setTrackMenuOpen(null);
                          void handleOpenTrackSource(track);
                        }}
                      >
                        Open source link
                      </button>
                      <button
                        type="button"
                        role="menuitem"
                        disabled={!canOpenLocal}
                        onClick={() => {
                          setTrackMenuOpen(null);
                          void handleOpenTrackLocalFile(track);
                        }}
                      >
                        Open local file
                      </button>
                    </span>
                  ) : null}
                </span>
              </span>
            </div>
          );
        }) : (
          <div className="detail-track-empty">
            No track matches this search or filter.
          </div>
        )}
      </div>
    </section>
  );
}

export default PlaylistDetailPage;
