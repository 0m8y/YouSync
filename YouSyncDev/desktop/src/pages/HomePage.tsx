import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import DetectionBadge from "../components/DetectionBadge";
import FolderSelector from "../components/FolderSelector";
import PlaylistPreviewCard from "../components/PlaylistPreviewCard";
import SmartPlaylistInput from "../components/SmartPlaylistInput";
import { useToast } from "../components/ToastProvider";
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
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<DetectionStatus>("empty");
  const [platform, setPlatform] = useState<PlatformId | null>(null);
  const [preview, setPreview] = useState<PlaylistPreview | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [folder, setFolder] = useState(readLastFolder);
  const previewRequestId = useRef(0);
  const { showToast } = useToast();

  const canAddPlaylist = status === "detected" && Boolean(folder.trim());
  const showForm = isPreviewLoading || status === "detected";

  useEffect(() => {
    let cancelled = false;
    const requestId = previewRequestId.current + 1;
    previewRequestId.current = requestId;
    const nextUrl = url.trim();

    setPreview(null);
    setIsPreviewLoading(false);

    if (!nextUrl) {
      setPlatform(null);
      setStatus("empty");
      return () => {
        cancelled = true;
      };
    }

    function isStale() {
      return cancelled || previewRequestId.current !== requestId;
    }

    async function updateDetection() {
      try {
        const detection = await detectPlaylist(nextUrl);

        if (isStale()) {
          return;
        }

        setPlatform(detection.platform === "unknown" ? null : detection.platform);

        if (detection.reason === "empty" || detection.reason === "unknown") {
          setStatus("empty");
          return;
        }

        if (!detection.supported) {
          setStatus("unsupported");
          return;
        }

        setStatus("loading");
        setIsPreviewLoading(true);

        await new Promise((resolve) => window.setTimeout(resolve, 0));

        if (isStale()) {
          return;
        }

        const nextPreview = await previewPlaylist(nextUrl);

        if (isStale()) {
          return;
        }

        setIsPreviewLoading(false);

        if (!nextPreview || nextPreview.supported === false) {
          setStatus("empty");
          setPreview(null);
          showToast(nextPreview?.message || "Playlist preview could not be loaded.", "error");
          return;
        }

        setPreview(nextPreview);
        setStatus("detected");
      } catch {
        if (!isStale()) {
          setIsPreviewLoading(false);
          setStatus("empty");
          setPreview(null);
          showToast("Playlist preview could not be loaded.", "error");
        }
      }
    }

    const timeout = window.setTimeout(() => {
      void updateDetection();
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [showToast, url]);

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

      showToast(result.message, "success");
      navigate("/playlists");
      return;
    }

    showToast(result.message, "error");
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
            <PlaylistPreviewCard loading={isPreviewLoading} preview={preview} />
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
    </section>
  );
}

export default HomePage;
