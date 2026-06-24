import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { convertFileSrc } from "@tauri-apps/api/core";
import { getPlatform } from "../data/mockData";
import type { PlaylistPreview } from "../types/playlist";

type PlaylistPreviewCardProps = {
  preview: PlaylistPreview | null;
  loading: boolean;
};

function PlaylistPreviewCard({ preview, loading }: PlaylistPreviewCardProps) {
  const coverSrc = useMemo(() => {
    if (!preview) {
      return null;
    }

    if (preview.coverPath) {
      return convertFileSrc(preview.coverPath);
    }

    return preview.coverUrl ?? null;
  }, [preview]);
  const [coverFailed, setCoverFailed] = useState(false);

  useEffect(() => {
    setCoverFailed(false);
  }, [coverSrc]);

  if (loading) {
    return (
      <div className="playlist-preview">
        <div className="preview-cover shimmer" />
        <div className="preview-body">
          <div className="shimmer text-wide" />
          <div className="shimmer text-short" />
          <div className="shimmer tag-placeholder" />
        </div>
      </div>
    );
  }

  if (!preview) {
    return null;
  }

  const platform = preview.platform === "unknown" ? null : getPlatform(preview.platform);
  const showCover = Boolean(coverSrc && !coverFailed);

  return (
    <div className="playlist-preview">
      <div
        className={`preview-cover ${preview.platform}`}
        aria-hidden="true"
      >
        {showCover ? (
          <img
            src={coverSrc ?? ""}
            alt=""
            onError={() => {
              console.warn("[YouSync] Failed to load playlist preview cover", {
                src: coverSrc,
                coverPath: preview.coverPath,
                coverUrl: preview.coverUrl,
              });
              setCoverFailed(true);
            }}
          />
        ) : (
          "♪"
        )}
      </div>
      <div className="preview-body">
        <h2>{preview.title}</h2>
        <p>{preview.tracks === null ? "" : `${preview.tracks} tracks`}</p>
        <span
          className="platform-tag"
          style={{ "--platform-accent": platform?.accent } as CSSProperties}
        >
          <span />
          {platform?.label}
        </span>
      </div>
    </div>
  );
}

export default PlaylistPreviewCard;
