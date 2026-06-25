import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { convertFileSrc } from "@tauri-apps/api/core";
import Toast from "../components/Toast";
import { getPlatform } from "../data/mockData";
import { USE_MOCK_PLAYLIST_STATUSES, getMockPlaylistDetail } from "../data/mockPlaylists";
import {
  cancelPlaylistSync,
  deletePlaylist,
  downloadMissing,
  getPlaylistDetails,
  getSyncStatus,
  openFolder,
  openSourceUrl,
  syncPlaylist
} from "../services/playlistService";
import type { LongTaskProgress, PlaylistDetail, SyncStatus } from "../services/playlistService";

const SYNC_STATUS_POLL_MS = 1500;

type PlaylistDetailPageProps = {
  playlistId: string;
  onBack: () => void;
};

function statusClass(status: string) {
  return status.toLowerCase();
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

function PlaylistDetailPage({ playlistId, onBack }: PlaylistDetailPageProps) {
  const [detail, setDetail] = useState<PlaylistDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncProgress, setSyncProgress] = useState<SyncStatus | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [coverFailed, setCoverFailed] = useState(false);

  async function loadDetail() {
    setIsLoading(true);
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

    async function load() {
      const nextDetail = USE_MOCK_PLAYLIST_STATUSES
        ? getMockPlaylistDetail(playlistId)
        : await getPlaylistDetails(playlistId);

      if (!cancelled) {
        setDetail(nextDetail);
        setIsLoading(false);
        setCoverFailed(false);
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [playlistId]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timeout = window.setTimeout(() => setToast(""), 3200);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  useEffect(() => {
    if (!isSyncing) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    async function pollSyncStatus() {
      const status = await getSyncStatus(playlistId);

      if (cancelled) {
        return;
      }

      setSyncProgress(status);

      if (status.status === "syncing") {
        timeoutId = window.setTimeout(pollSyncStatus, SYNC_STATUS_POLL_MS);
        return;
      }

      if (status.status === "completed") {
        await loadDetail();
        if (!cancelled) {
          if (status.message?.includes("failed")) {
            setToast(status.message);
          }
          setIsSyncing(false);
          setSyncProgress(null);
        }
        return;
      }

      if (status.status === "error") {
        await loadDetail();
        if (!cancelled) {
          setToast(status.message || "Sync could not be completed.");
          setIsSyncing(false);
          setSyncProgress(null);
        }
        return;
      }

      if (status.status === "cancelled") {
        await loadDetail();
        if (!cancelled) {
          setSyncProgress(status);
        }
        return;
      }

      setIsSyncing(false);
      setSyncProgress(null);
    }

    void pollSyncStatus().catch((error) => {
      if (!cancelled) {
        setToast(error instanceof Error ? error.message : String(error));
        setIsSyncing(false);
        setSyncProgress(null);
      }
    });

    return () => {
      cancelled = true;

      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [isSyncing, playlistId]);

  useEffect(() => {
    if (syncProgress?.status !== "cancelled") {
      return;
    }

    const timeout = window.setTimeout(() => {
      setIsSyncing(false);
      setSyncProgress(null);
    }, 2200);

    return () => window.clearTimeout(timeout);
  }, [syncProgress]);

  const playlist = detail?.playlist ?? null;
  const platform = playlist ? getPlatform(playlist.platform) : null;
  const coverSrc = useMemo(
    () => (playlist?.coverPath ? convertFileSrc(playlist.coverPath) : null),
    [playlist?.coverPath]
  );
  const showCover = Boolean(coverSrc && !coverFailed);

  async function handleSyncNow() {
    if (isSyncing) {
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
      return;
    }

    setIsSyncing(true);
    setSyncProgress({
      playlistId,
      status: "syncing",
      phase: "syncing",
      message: "Syncing playlist...",
    });
  }

  async function handleDownloadMissing() {
    setMenuOpen(false);

    if (isSyncing) {
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
      return;
    }

    setIsSyncing(true);
    setSyncProgress({
      playlistId,
      status: "syncing",
      phase: "downloading",
      message: "Preparing downloads...",
    });
  }

  async function handleCancelSync() {
    if (!isSyncing) {
      return;
    }

    const result = await cancelPlaylistSync(playlistId);

    if (!result.ok) {
      setToast(result.message);
      return;
    }

    setSyncProgress({
      ...(syncProgress ?? { playlistId }),
      playlistId,
      status: "cancelled",
      phase: "cancelled",
      currentTrack: "",
      message: result.message || "Sync cancelled.",
    });
    await loadDetail();
  }

  async function handleRemovePlaylist() {
    setMenuOpen(false);

    if (isSyncing) {
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
      onBack();
      return;
    }

    const result = await deletePlaylist(playlistId);

    if (!result.ok) {
      setToast(result.message);
      return;
    }

    onBack();
  }

  async function handleOpenFolder() {
    if (!playlist) {
      return;
    }

    const opened = await openFolder(playlist.path);
    if (!opened) {
      setToast("Folder could not be opened.");
    }
  }

  async function handleOpenSource() {
    if (!playlist?.sourceUrl) {
      return;
    }

    const opened = await openSourceUrl(playlist.sourceUrl);
    if (!opened) {
      setToast("Source could not be opened.");
    }
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
            <div className="detail-menu-wrap" onMouseLeave={() => setMenuOpen(false)}>
              <button
                className="detail-btn detail-dots"
                type="button"
                aria-label="More actions"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((open) => !open)}
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
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      {isSyncing && syncProgress ? (
        <div className="detail-progress" role="status">
          <span className="sync-spinner" aria-hidden="true" />
          <span>{progressLabel(syncProgress)}</span>
        </div>
      ) : null}

      <div className="detail-track-header" aria-hidden="true">
        <span>#</span>
        <span>Title</span>
        <span>Artist</span>
        <span>Status</span>
        <span>Duration</span>
      </div>

      <div className="detail-track-table">
        {detail.tracks.map((track) => (
          <div className="detail-track-row" key={`${track.index}-${track.title}`}>
            <span className="detail-track-num">{track.index}</span>
            <span className="detail-track-title">{track.title}</span>
            <span className="detail-track-artist">{track.artist || "—"}</span>
            <span className={`detail-track-status ${statusClass(track.status)}`}>
              <span />
              {track.status}
            </span>
            <span className="detail-track-duration">{track.duration || "—"}</span>
          </div>
        ))}
      </div>

      {toast ? <Toast message={toast} /> : null}
    </section>
  );
}

export default PlaylistDetailPage;
