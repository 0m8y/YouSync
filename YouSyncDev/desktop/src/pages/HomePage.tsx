import { useEffect, useState } from "react";
import DetectionBadge from "../components/DetectionBadge";
import FolderSelector from "../components/FolderSelector";
import PlaylistPreviewCard from "../components/PlaylistPreviewCard";
import SmartPlaylistInput from "../components/SmartPlaylistInput";
import Toast from "../components/Toast";
import {
  PLAYLISTS_UPDATED_EVENT,
  addPlaylist,
  detectPlaylist,
  listPlaylists,
  previewPlaylist
} from "../services/playlistService";
import type { DetectionStatus, PlatformId, PlaylistPreview } from "../types/playlist";

const LAST_FOLDER_KEY = "yousync:last-folder";

function readLastFolder() {
  try {
    return window.localStorage.getItem(LAST_FOLDER_KEY) ?? "";
  } catch {
    return "";
  }
}

function HomePage() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<DetectionStatus>("empty");
  const [platform, setPlatform] = useState<PlatformId | null>(null);
  const [preview, setPreview] = useState<PlaylistPreview | null>(null);
  const [folder, setFolder] = useState(readLastFolder);
  const [toast, setToast] = useState("");

  const canAddPlaylist = status === "detected" && Boolean(folder.trim());
  const showForm = status === "loading" || status === "detected";

  useEffect(() => {
    let cancelled = false;

    async function updateDetection() {
      const detection = await detectPlaylist(url);

      if (cancelled) {
        return;
      }

      setPlatform(detection.platform === "unknown" ? null : detection.platform);
      setPreview(null);

      if (detection.reason === "empty" || detection.reason === "unknown") {
        setStatus("empty");
        return;
      }

      if (!detection.supported) {
        setStatus("unsupported");
        return;
      }

      setStatus("loading");
      const nextPreview = await previewPlaylist(url);

      if (!cancelled) {
        setPreview(nextPreview);
        setStatus(nextPreview?.supported === false ? "empty" : "detected");
      }
    }

    void updateDetection();

    return () => {
      cancelled = true;
    };
  }, [url]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timeout = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  async function handleAddPlaylist() {
    if (!canAddPlaylist) {
      return;
    }

    const result = await addPlaylist({ url, folder });

    console.info("[YouSync] addPlaylist response", {
      ok: result.ok,
      message: result.message,
      playlist: result.playlist,
      coverPath: result.playlist?.coverPath,
    });

    if (result.ok) {
      try {
        window.localStorage.setItem(LAST_FOLDER_KEY, folder);
      } catch {
        // localStorage may be unavailable in restricted webviews.
      }

      const playlists = await listPlaylists();
      console.info("[YouSync] listPlaylists response after add", {
        playlists,
        addedPlaylistId: result.playlist?.id,
        addedCoverPathFromAdd: result.playlist?.coverPath,
        addedCoverPathFromList: playlists.find((playlist) => playlist.id === result.playlist?.id)?.coverPath,
      });

      const mergedPlaylists = result.playlist
        ? playlists.map((playlist) =>
            playlist.id === result.playlist?.id && !playlist.coverPath
              ? { ...playlist, coverPath: result.playlist?.coverPath }
              : playlist
          )
        : playlists;
      const hasAddedPlaylist = result.playlist
        ? mergedPlaylists.some((playlist) => playlist.id === result.playlist?.id)
        : true;

      window.dispatchEvent(
        new CustomEvent(PLAYLISTS_UPDATED_EVENT, {
          detail: hasAddedPlaylist || !result.playlist
            ? mergedPlaylists
            : [...mergedPlaylists, result.playlist],
        })
      );
    }

    setToast(result.message);
  }

  return (
    <section className="home-page" aria-label="Add playlist">
      <div className="home-center">
        <h1>Add Playlist</h1>
        <p className="home-subtitle">Paste a playlist link to sync it locally</p>

        <SmartPlaylistInput
          onChange={setUrl}
          platform={platform}
          status={status}
          value={url}
        />

        <DetectionBadge platform={platform} preview={preview} status={status} />

        {showForm ? (
          <>
            <PlaylistPreviewCard loading={status === "loading"} preview={preview} />
            <FolderSelector onChange={setFolder} value={folder} />
            <button
              className="add-playlist-button"
              disabled={!canAddPlaylist}
              onClick={handleAddPlaylist}
              type="button"
            >
              Add Playlist
            </button>
          </>
        ) : null}
      </div>

      {toast ? <Toast message={toast} /> : null}
    </section>
  );
}

export default HomePage;
