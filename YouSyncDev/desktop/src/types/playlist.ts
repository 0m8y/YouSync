import type {
  Platform as ServicePlatform,
  PlaylistStatus,
  PlaylistSummary
} from "../services/playlistService";

export type PlatformId = Exclude<ServicePlatform, "unknown">;

export type DetectionStatus = "empty" | "loading" | "detected" | "unsupported";

export type Platform = {
  id: PlatformId;
  label: string;
  accent: string;
};

export type PlaylistPreview = import("../services/playlistService").PlaylistPreview;
export type { PlaylistStatus };
export type PlaylistListItem = PlaylistSummary;
