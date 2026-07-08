import type { CSSProperties } from "react";
import { getPlatform } from "../data/mockData";
import type { DetectionStatus, PlatformId, PlaylistPreview } from "../types/playlist";

type DetectionBadgeProps = {
  platform: PlatformId | null;
  preview: PlaylistPreview | null;
  status: DetectionStatus;
};

function DetectionBadge({ platform, preview, status }: DetectionBadgeProps) {
  if (status === "empty" || !platform) {
    return null;
  }

  if (status === "loading") {
    return (
      <div className="detection-badge muted">
        <span className="badge-loader" aria-hidden="true">◌</span>
        <span>Fetching playlist info...</span>
      </div>
    );
  }

  if (status === "unsupported") {
    return (
      <div className="support-notice">
        <span className="notice-icon" aria-hidden="true">◷</span>
        <div>
          <strong>SoundCloud support coming soon</strong>
          <p>SoundCloud playlists are not supported yet. Try a YouTube, Spotify, or Apple Music link instead.</p>
        </div>
      </div>
    );
  }

  const platformMeta = getPlatform(platform);

  return (
    <div
      className="detection-badge"
      style={{ "--platform-accent": platformMeta?.accent } as CSSProperties}
    >
      <span className="badge-dot" />
      <span>{platformMeta?.label} playlist detected</span>
      {preview ? <em>{preview.title}</em> : null}
    </div>
  );
}

export default DetectionBadge;
