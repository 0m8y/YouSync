import { open } from "@tauri-apps/plugin-dialog";

type FolderSelectorProps = {
  value: string;
  onChange: (value: string) => void;
};

function FolderSelector({ value, onChange }: FolderSelectorProps) {
  async function handleBrowse() {
    const selected = await open({
      directory: true,
      multiple: false,
    });

    if (typeof selected === "string") {
      onChange(selected);
    }
  }

  return (
    <div className="folder-section">
      <label htmlFor="save-folder">Destination Folder</label>
      <div className="folder-input-row">
        <div className="folder-field">
          <span aria-hidden="true">□</span>
          <input
            id="save-folder"
            onChange={(event) => onChange(event.target.value)}
            placeholder="Select a folder..."
            type="text"
            value={value}
          />
        </div>
        <button className="browse-btn" onClick={handleBrowse} type="button">
          Browse
        </button>
      </div>
      {value.trim() ? null : <p>No folder selected</p>}
    </div>
  );
}

export default FolderSelector;
