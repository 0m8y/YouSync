import type { PlaylistDetail, PlaylistSummary } from "../services/playlistService";

export const USE_MOCK_PLAYLIST_STATUSES = import.meta.env.VITE_YOUSYNC_MOCK_STATUSES === "1";

export const mockPlaylists: PlaylistSummary[] = [
  {
    id: "mock-synced",
    title: "Synced Reference",
    path: "/Users/omay/Music/YouSync/Synced",
    platform: "spotify",
    tracks: 12,
    status: { type: "synced", label: "Synced" },
    lastSynced: "2 min ago",
  },
  {
    id: "mock-missing",
    title: "Missing Downloads",
    path: "/Users/omay/Music/YouSync/Missing",
    platform: "youtube",
    tracks: 18,
    status: { type: "missing", label: "18 missing" },
    lastSynced: "Not synced yet",
  },
  {
    id: "mock-partial",
    title: "Partial Playlist",
    path: "/Users/omay/Music/YouSync/Partial",
    platform: "apple",
    tracks: 24,
    status: { type: "partial", label: "7 missing" },
    lastSynced: "Yesterday",
  },
  {
    id: "mock-error",
    title: "Playlist With Errors",
    path: "/Users/omay/Music/YouSync/Error",
    platform: "spotify",
    tracks: 9,
    status: { type: "error", label: "2 errors" },
    lastSynced: "1 hr ago",
  },
  {
    id: "mock-syncing",
    title: "Sync In Progress",
    path: "/Users/omay/Music/YouSync/Syncing",
    platform: "youtube",
    tracks: 31,
    status: { type: "syncing", label: "Syncing...", progress: 45 },
    lastSynced: "Syncing...",
  },
];

export const mockPlaylistDetail: PlaylistDetail = {
  playlist: {
    ...mockPlaylists[2],
    sourceUrl: "https://example.com/mock-playlist",
  },
  tracks: [
    {
      index: 1,
      title: "Fully Ready Track",
      artist: "YouSync",
      status: "Synced",
      duration: "3:12",
    },
    {
      index: 2,
      title: "Downloaded Without Metadata",
      artist: "YouSync",
      status: "Downloaded",
      duration: "4:05",
    },
    {
      index: 3,
      title: "Metadata Only",
      artist: "YouSync",
      status: "Metadata",
      duration: "—",
    },
    {
      index: 4,
      title: "Missing File",
      artist: "—",
      status: "Missing",
      duration: "—",
    },
    {
      index: 5,
      title: "Failed Download",
      artist: "YouSync",
      status: "Error",
      duration: "2:58",
    },
  ],
};

export function getMockPlaylistDetail(playlistId: string): PlaylistDetail {
  const playlist = mockPlaylists.find((item) => item.id === playlistId) ?? mockPlaylists[0];

  return {
    ...mockPlaylistDetail,
    playlist: {
      ...playlist,
      sourceUrl: "https://example.com/mock-playlist",
    },
  };
}
