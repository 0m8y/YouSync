import type { Platform, PlatformId } from "../types/playlist";

export const platforms: Platform[] = [
  { id: "youtube", label: "YouTube", accent: "#ff3c3c" },
  { id: "spotify", label: "Spotify", accent: "#1aa34a" },
  { id: "apple", label: "Apple Music", accent: "#ff5fa8" },
  { id: "deezer", label: "Deezer", accent: "#a238ff" },
  { id: "soundcloud", label: "SoundCloud", accent: "#6a6a72" }
];

export function getPlatform(platformId: PlatformId) {
  return platforms.find((platform) => platform.id === platformId);
}
