import { invoke } from "@tauri-apps/api/core";

export type Platform = "youtube" | "spotify" | "apple" | "soundcloud" | "unknown";

export const PLAYLISTS_UPDATED_EVENT = "yousync:playlists-updated";

export type PlaylistDetection = {
  platform: Platform;
  supported: boolean;
  reason?: "empty" | "unsupported" | "unknown";
};

export type PlaylistPreview = {
  title: string;
  tracks: number | null;
  platform: Platform;
  coverUrl?: string | null;
  coverPath?: string | null;
  supported?: boolean;
  message?: string;
};

export type AddPlaylistRequest = {
  url: string;
  folder: string;
};

export type AddPlaylistResult = {
  ok: boolean;
  message: string;
  playlist?: PlaylistSummary;
};

export type DeletePlaylistResult = {
  ok: boolean;
  message: string;
};

export type RedownloadTrackResult = {
  ok: boolean;
  playlistId: string;
  trackIndex: number;
  message?: string;
};

export type CancelPlaylistSyncResult = {
  ok: boolean;
  playlistId: string;
  message: string;
};

export type CancelSyncAllResult = {
  ok: boolean;
  message: string;
};

export type SyncStartResult = {
  started: boolean;
  playlistId: string;
  message?: string;
};

export type SyncAllStartResult = {
  started: boolean;
  playlistIds: string[];
  message?: string;
};

export type LongTaskPhase = "idle" | "queued" | "syncing" | "downloading" | "completed" | "error" | "cancelled";
export type LongTaskJobType = "single" | "all" | "download_missing" | null;

export type PlaylistTaskProgress = {
  status: "idle" | "queued" | "syncing" | "completed" | "error" | "cancelled";
  phase?: LongTaskPhase;
  current?: number;
  total?: number;
  currentTrack?: string;
  failedCount?: number;
  message?: string;
};

export type LongTaskProgress = PlaylistTaskProgress & {
  jobType?: LongTaskJobType;
  playlistId?: string | null;
  playlistTitle?: string;
  playlistCurrent?: number | null;
  playlistTotal?: number | null;
  playlists?: Record<string, PlaylistTaskProgress>;
};

export type SyncStatus = LongTaskProgress & {
  playlistId: string;
};

export type SyncAllStatus = LongTaskProgress & {
  playlistIds: string[];
};

export type SyncTasksStatus = {
  playlists: Record<string, SyncStatus>;
  syncAll?: SyncAllStatus | null;
};

export type PlaylistStatus =
  | { type: "synced"; label: string }
  | { type: "syncing"; label: string; progress: number }
  | { type: "error"; label: string }
  | { type: "missing"; label: string }
  | { type: "partial"; label: string }
  | { type: "stale"; label: string }
  | { type: "empty"; label: string };

export type PlaylistSummary = {
  id: string;
  title: string;
  path: string;
  platform: Exclude<Platform, "unknown">;
  tracks: number;
  coverPath?: string | null;
  sourceUrl?: string | null;
  status: PlaylistStatus;
  lastSynced: string;
};

export type PlaylistTrack = {
  index: number;
  title: string;
  artist: string;
  status: "Synced" | "Downloaded" | "Metadata" | "Missing" | "Error";
  duration: string;
  url?: string | null;
  sourceUrl?: string | null;
  localPath?: string | null;
  isDownloaded?: boolean;
};

export type PlaylistDetail = {
  playlist: PlaylistSummary & {
    sourceUrl: string;
  };
  tracks: PlaylistTrack[];
};

function bridgeError(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}

export async function detectPlaylist(url: string): Promise<PlaylistDetection> {
  try {
    return await invoke<PlaylistDetection>("detect_playlist", { url });
  } catch (error) {
    return {
      platform: "unknown",
      supported: false,
      reason: "unknown"
    };
  }
}

export async function previewPlaylist(url: string): Promise<PlaylistPreview | null> {
  try {
    return await invoke<PlaylistPreview | null>("preview_playlist", { url });
  } catch {
    return null;
  }
}

export async function addPlaylist(
  urlOrRequest: string | AddPlaylistRequest,
  folder?: string
): Promise<AddPlaylistResult> {
  const request =
    typeof urlOrRequest === "string"
      ? { url: urlOrRequest, folder: folder ?? "" }
      : urlOrRequest;

  try {
    const result = await invoke<AddPlaylistResult>("add_playlist", request);
    console.info("[YouSync] bridge add_playlist result", {
      request,
      result,
      coverPath: result.playlist?.coverPath,
    });
    return result;
  } catch (error) {
    return {
      ok: false,
      message: bridgeError(error)
    };
  }
}

export async function listPlaylists(): Promise<PlaylistSummary[]> {
  try {
    const playlists = await invoke<PlaylistSummary[]>("list_playlists");
    console.info("[YouSync] bridge list_playlists result", playlists.map((playlist) => ({
      id: playlist.id,
      title: playlist.title,
      coverPath: playlist.coverPath,
      tracks: playlist.tracks,
      status: playlist.status,
    })));
    return playlists;
  } catch {
    return [];
  }
}

export async function getPlaylistDetails(playlistId: string): Promise<PlaylistDetail | null> {
  try {
    return await invoke<PlaylistDetail>("get_playlist_details", { playlistId });
  } catch (error) {
    console.warn("[YouSync] bridge get_playlist_details failed", bridgeError(error));
    return null;
  }
}

export async function syncPlaylist(playlistId: string): Promise<SyncStartResult> {
  try {
    return await invoke<SyncStartResult>("sync_playlist", { playlistId });
  } catch (error) {
    console.warn("[YouSync] bridge sync_playlist failed", bridgeError(error));
    return {
      started: false,
      playlistId,
      message: bridgeError(error),
    };
  }
}

export async function downloadMissing(playlistId: string): Promise<SyncStartResult> {
  try {
    return await invoke<SyncStartResult>("download_missing", { playlistId });
  } catch (error) {
    console.warn("[YouSync] bridge download_missing failed", bridgeError(error));
    return {
      started: false,
      playlistId,
      message: bridgeError(error),
    };
  }
}

export async function redownloadTrack(playlistId: string, trackIndex: number): Promise<RedownloadTrackResult> {
  try {
    return await invoke<RedownloadTrackResult>("redownload_track", { playlistId, trackIndex });
  } catch (error) {
    console.warn("[YouSync] bridge redownload_track failed", bridgeError(error));
    return {
      ok: false,
      playlistId,
      trackIndex,
      message: bridgeError(error),
    };
  }
}

export async function deletePlaylist(playlistId: string): Promise<DeletePlaylistResult> {
  try {
    return await invoke<DeletePlaylistResult>("delete_playlist", { playlistId });
  } catch (error) {
    console.warn("[YouSync] bridge delete_playlist failed", bridgeError(error));
    return {
      ok: false,
      message: bridgeError(error),
    };
  }
}

export async function cancelPlaylistSync(playlistId: string): Promise<CancelPlaylistSyncResult> {
  try {
    return await invoke<CancelPlaylistSyncResult>("cancel_playlist_sync", { playlistId });
  } catch (error) {
    console.warn("[YouSync] bridge cancel_playlist_sync failed", bridgeError(error));
    return {
      ok: false,
      playlistId,
      message: bridgeError(error),
    };
  }
}

export async function cancelSyncAll(): Promise<CancelSyncAllResult> {
  try {
    return await invoke<CancelSyncAllResult>("cancel_sync_all");
  } catch (error) {
    console.warn("[YouSync] bridge cancel_sync_all failed", bridgeError(error));
    return {
      ok: false,
      message: bridgeError(error),
    };
  }
}


export function resolvePlaylistFolderPath(path: string): string {
  const trimmedPath = path.trim();

  if (!trimmedPath) {
    return trimmedPath;
  }

  const unixMarker = "/.yousync/";
  const windowsMarker = "\\.yousync\\";
  const unixIndex = trimmedPath.lastIndexOf(unixMarker);

  if (unixIndex >= 0) {
    return trimmedPath.slice(0, unixIndex);
  }

  const windowsIndex = trimmedPath.lastIndexOf(windowsMarker);

  if (windowsIndex >= 0) {
    return trimmedPath.slice(0, windowsIndex);
  }

  if (trimmedPath.endsWith("/.yousync")) {
    return trimmedPath.slice(0, -"/.yousync".length);
  }

  if (trimmedPath.endsWith("\\.yousync")) {
    return trimmedPath.slice(0, -"\\.yousync".length);
  }

  return trimmedPath;
}

export async function openFolder(path: string): Promise<boolean> {
  try {
    await invoke("open_folder", { path });
    return true;
  } catch (error) {
    console.warn("[YouSync] open_folder failed", bridgeError(error));
    return false;
  }
}

export async function openSourceUrl(url: string): Promise<boolean> {
  try {
    await invoke("open_url", { url });
    return true;
  } catch (error) {
    console.warn("[YouSync] open_url failed", bridgeError(error));
    return false;
  }
}

export async function openLocalFile(path: string): Promise<boolean> {
  try {
    await invoke("open_local_file", { path });
    return true;
  } catch (error) {
    console.warn("[YouSync] open_local_file failed", bridgeError(error));
    return false;
  }
}

export async function getSyncStatus(playlistId: string): Promise<SyncStatus> {
  try {
    return await invoke<SyncStatus>("get_sync_status", { playlistId });
  } catch (error) {
    console.warn("[YouSync] bridge get_sync_status failed", bridgeError(error));
    return {
      playlistId,
      status: "error",
      message: bridgeError(error),
    };
  }
}

export async function syncAllPlaylists(): Promise<SyncAllStartResult> {
  try {
    return await invoke<SyncAllStartResult>("sync_all_playlists");
  } catch (error) {
    console.warn("[YouSync] bridge sync_all_playlists failed", bridgeError(error));
    return {
      started: false,
      playlistIds: [],
      message: bridgeError(error),
    };
  }
}

export async function getSyncAllStatus(): Promise<SyncAllStatus> {
  try {
    return await invoke<SyncAllStatus>("get_sync_all_status");
  } catch (error) {
    console.warn("[YouSync] bridge get_sync_all_status failed", bridgeError(error));
    return {
      status: "error",
      playlistIds: [],
      message: bridgeError(error),
    };
  }
}

export async function getSyncTasksStatus(): Promise<SyncTasksStatus> {
  try {
    return await invoke<SyncTasksStatus>("get_sync_tasks_status");
  } catch (error) {
    console.warn("[YouSync] bridge get_sync_tasks_status failed", bridgeError(error));
    return {
      playlists: {},
      syncAll: null,
    };
  }
}
