import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { convertFileSrc } from "@tauri-apps/api/core";
import { getPlatform } from "../data/mockData";
import type { PlaylistListItem } from "../types/playlist";

type PlaylistRowProps = {
  playlist: PlaylistListItem;
  isSyncing?: boolean;
  onSync?: (playlistId: string) => void;
};

function PlaylistRow({ playlist, isSyncing = false, onSync }: PlaylistRowProps) {
  const platform = getPlatform(playlist.platform);
  const status = playlist.status;
  const coverUrl = useMemo(
    () => (playlist.coverPath ? convertFileSrc(playlist.coverPath) : null),
    [playlist.coverPath],
  );
  const [coverFailed, setCoverFailed] = useState(false);

  useEffect(() => {
    setCoverFailed(false);

    if (playlist.coverPath && coverUrl) {
      console.info("[YouSync] Playlist cover asset URL", {
        title: playlist.title,
        coverPath: playlist.coverPath,
        src: coverUrl,
      });
    }
  }, [coverUrl, playlist.coverPath, playlist.title]);

  const showCover = Boolean(coverUrl && !coverFailed);

  return (
    <div className={`playlist-row ${isSyncing ? "syncing" : status.type}`}>
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
        <div className="playlist-path">{playlist.path}</div>
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
        {isSyncing ? (
          <>
            <span className="sync-spinner" aria-hidden="true" />
            <span>Syncing...</span>
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
        <button type="button" aria-label={`More actions for ${playlist.title}`}>⋮</button>
      </div>
    </div>
  );
}

export default PlaylistRow;
