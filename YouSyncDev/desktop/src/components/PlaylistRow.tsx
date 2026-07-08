import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { convertFileSrc } from "@tauri-apps/api/core";
import { getPlatform } from "../data/mockData";
import type { LongTaskProgress } from "../services/playlistService";
import { debugLog } from "../services/settingsService";
import type { PlaylistListItem } from "../types/playlist";
import { formatPathForDisplay } from "../utils/pathDisplay";

type PlaylistRowProps = {
  playlist: PlaylistListItem;
  isSyncing?: boolean;
  progress?: LongTaskProgress | null;
  onOpen?: (playlistId: string) => void;
  onSync?: (playlistId: string) => void;
  onCancelSync?: (playlistId: string) => void;
  onDownloadMissing?: (playlistId: string) => void;
  onOpenFolder?: (playlistId: string) => void;
  onOpenSource?: (playlistId: string) => void;
  onChangeLocation?: (playlistId: string) => void;
  onRemove?: (playlistId: string) => void;
  onRemoveWithLocalFiles?: (playlistId: string) => void;
};

function syncLabel(progress?: LongTaskProgress | null) {
  if (progress?.status === "queued" || progress?.phase === "queued") {
    return progress.message || "Queued";
  }

  if (progress?.status === "completed" || progress?.phase === "completed") {
    return progress.message || "Completed";
  }

  if (progress?.status === "error" || progress?.phase === "error") {
    return progress.message || "Error";
  }

  if (progress?.status === "cancelled" || progress?.phase === "cancelled") {
    return progress.message || "Cancelled";
  }

  if (progress?.total && progress.total > 0) {
    const current = progress.current ?? 0;
    const verb = progress.phase === "downloading" ? "Downloading" : "Syncing";
    return verb + " " + current + "/" + progress.total;
  }

  return progress?.message || "Syncing...";
}

function PlaylistRow({
  playlist,
  isSyncing = false,
  progress = null,
  onOpen,
  onSync,
  onCancelSync,
  onDownloadMissing,
  onOpenFolder,
  onOpenSource,
  onChangeLocation,
  onRemove,
  onRemoveWithLocalFiles,
}: PlaylistRowProps) {
  const platform = getPlatform(playlist.platform);
  const status = playlist.status;
  const coverUrl = useMemo(
    () => (playlist.coverPath ? convertFileSrc(playlist.coverPath) : null),
    [playlist.coverPath],
  );
  const [coverFailed, setCoverFailed] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setCoverFailed(false);

    if (playlist.coverPath && coverUrl) {
      debugLog("[YouSync] Playlist cover asset URL", {
        title: playlist.title,
        coverPath: playlist.coverPath,
        src: coverUrl,
      });
    }
  }, [coverUrl, playlist.coverPath, playlist.title]);

  const showCover = Boolean(coverUrl && !coverFailed);
  const hasProgress = Boolean(progress);
  const isErrorProgress = progress?.status === "error";
  const rowState = isSyncing ? "syncing" : isErrorProgress ? "error" : status.type;
  const displayPath = formatPathForDisplay(playlist.path);

  return (
    <div
      className={`playlist-row ${rowState}`}
      onClick={() => onOpen?.(playlist.id)}
      onMouseLeave={() => setMenuOpen(false)}
    >
      <div
        className={`playlist-thumb ${playlist.platform}`}
        aria-hidden="true"
        data-cover-src={coverUrl ?? undefined}
      >
        {showCover ? (
          <img
            src={coverUrl ?? ""}
            alt=""
            onError={() => {
              console.warn("[YouSync] Failed to load playlist cover", {
                src: coverUrl,
                coverPath: playlist.coverPath,
              });
              setCoverFailed(true);
            }}
          />
        ) : (
          "♪"
        )}
      </div>

      <div className="playlist-info">
        <div className="playlist-name">{playlist.title}</div>
        <div className="playlist-path" title={playlist.path}>{displayPath}</div>
      </div>

      <div className="playlist-platform">
        <span
          className="platform-tag"
          style={{ "--platform-accent": platform?.accent } as CSSProperties}
        >
          <span />
          {platform?.label}
        </span>
      </div>

      <div className="playlist-tracks">{playlist.tracks} tracks</div>

      <div className="playlist-status">
        {hasProgress ? (
          <>
            {progress?.status === "syncing" ? (
              <span className="sync-spinner" aria-hidden="true" />
            ) : (
              <span className="status-dot" />
            )}
            <span>{syncLabel(progress)}</span>
          </>
        ) : status.type === "syncing" ? (
          <>
            <span className="sync-spinner" aria-hidden="true" />
            <span>{status.label}</span>
          </>
        ) : (
          <>
            <span className="status-dot" />
            <span>{status.label}</span>
          </>
        )}
      </div>

      <div className="playlist-date">{playlist.lastSynced}</div>

      <div className="playlist-actions">
        <button
          type="button"
          aria-label={`Sync ${playlist.title}`}
          disabled={isSyncing}
          onClick={(event) => {
            event.stopPropagation();
            onSync?.(playlist.id);
          }}
        >
          ↻
        </button>
        {isSyncing ? (
          <button
            className="stop-btn"
            type="button"
            title="Stop sync"
            aria-label={`Stop sync for ${playlist.title}`}
            onClick={(event) => {
              event.stopPropagation();
              onCancelSync?.(playlist.id);
            }}
          >
            ⏹
          </button>
        ) : null}
        {!isSyncing ? (
          <div
            className="playlist-menu-wrap"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              aria-label={`More actions for ${playlist.title}`}
              aria-expanded={menuOpen}
              onClick={(event) => {
                event.stopPropagation();
                setMenuOpen((open) => !open);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  event.stopPropagation();
                  setMenuOpen(false);
                }
              }}
            >
              ⋮
            </button>
            {menuOpen ? (
              <div className="detail-menu playlist-menu" role="menu">
                {isErrorProgress ? (
                  <button
                    type="button"
                    role="menuitem"
                    onClick={(event) => {
                      event.stopPropagation();
                      setMenuOpen(false);
                      onSync?.(playlist.id);
                    }}
                  >
                    Retry sync
                  </button>
                ) : null}
                <button
                  type="button"
                  role="menuitem"
                  onClick={(event) => {
                    event.stopPropagation();
                    setMenuOpen(false);
                    onDownloadMissing?.(playlist.id);
                  }}
                >
                  Download missing
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={(event) => {
                    event.stopPropagation();
                    setMenuOpen(false);
                    onOpenFolder?.(playlist.id);
                  }}
                >
                  Open folder
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={(event) => {
                    event.stopPropagation();
                    setMenuOpen(false);
                    onOpenSource?.(playlist.id);
                  }}
                >
                  Open source link
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={(event) => {
                    event.stopPropagation();
                    setMenuOpen(false);
                    onChangeLocation?.(playlist.id);
                  }}
                >
                  Change playlist location
                </button>
                <div className="menu-separator" role="separator" />
                <button
                  className="menu-danger"
                  type="button"
                  role="menuitem"
                  onClick={(event) => {
                    event.stopPropagation();
                    setMenuOpen(false);
                    onRemove?.(playlist.id);
                  }}
                >
                  Remove playlist
                </button>
                <button
                  className="menu-danger menu-danger-strong"
                  type="button"
                  role="menuitem"
                  onClick={(event) => {
                    event.stopPropagation();
                    setMenuOpen(false);
                    onRemoveWithLocalFiles?.(playlist.id);
                  }}
                >
                  Remove playlist + local files
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default PlaylistRow;
