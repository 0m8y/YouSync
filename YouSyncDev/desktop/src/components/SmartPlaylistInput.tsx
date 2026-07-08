import type { DetectionStatus, PlatformId } from "../types/playlist";

type SmartPlaylistInputProps = {
  value: string;
  status: DetectionStatus;
  platform: PlatformId | null;
  onChange: (value: string) => void;
};

function SmartPlaylistInput({ value, status, platform, onChange }: SmartPlaylistInputProps) {
  const detected = status === "detected" && platform !== "soundcloud";
  const loading = status === "loading";

  return (
    <div className={`smart-input-wrap${detected || loading ? " detected" : ""}`}>
      <input
        className="smart-input"
        onChange={(event) => onChange(event.target.value)}
        placeholder="Paste playlist link..."
        spellCheck={false}
        type="url"
        value={value}
      />
      <span className={`input-status-icon${loading ? " spinning" : ""}`} aria-hidden="true">
        {loading ? "◌" : detected ? "✓" : status === "unsupported" ? "×" : "⌁"}
      </span>
      {detected || loading ? <span className="input-ring" /> : null}
    </div>
  );
}

export default SmartPlaylistInput;
