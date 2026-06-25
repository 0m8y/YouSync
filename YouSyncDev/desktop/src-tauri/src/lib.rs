use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use tauri::State;

fn python_executable() -> PathBuf {
    let project_root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let venv_python = if cfg!(windows) {
        project_root.join(".venv/Scripts/python.exe")
    } else {
        project_root.join(".venv/bin/python")
    };

    if venv_python.exists() {
        return venv_python;
    }

    if cfg!(windows) {
        PathBuf::from("python")
    } else {
        PathBuf::from("python3")
    }
}

struct WorkerProcess {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

impl WorkerProcess {
    fn new() -> Result<Self, String> {
        let script_path = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../python/yousync_worker.py");
        let python = python_executable();
        let mut child = Command::new(&python)
            .arg("-u")
            .arg(&script_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|error| {
                format!(
                    "Failed to start Python worker with '{}': {error}",
                    python.display()
                )
            })?;

        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| "Failed to open Python worker stdin".to_string())?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "Failed to open Python worker stdout".to_string())?;

        Ok(Self {
            child,
            stdin,
            stdout: BufReader::new(stdout),
        })
    }
}

impl Drop for WorkerProcess {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

struct WorkerState {
    process: Mutex<WorkerProcess>,
    next_id: AtomicU64,
}

impl WorkerState {
    fn new() -> Result<Self, String> {
        Ok(Self {
            process: Mutex::new(WorkerProcess::new()?),
            next_id: AtomicU64::new(1),
        })
    }
}

fn call_python_worker(state: &WorkerState, command: &str, payload: Value) -> Result<Value, String> {
    let request_id = state.next_id.fetch_add(1, Ordering::Relaxed).to_string();
    let request = json!({
        "id": request_id,
        "command": command,
        "payload": payload,
    });
    let request_line = serde_json::to_string(&request)
        .map_err(|error| format!("Failed to serialize worker request: {error}"))?
        + "\n";
    let mut process = state
        .process
        .lock()
        .map_err(|_| "Python worker lock is poisoned".to_string())?;

    process
        .stdin
        .write_all(request_line.as_bytes())
        .map_err(|error| format!("Failed to write Python worker request: {error}"))?;
    process
        .stdin
        .flush()
        .map_err(|error| format!("Failed to flush Python worker request: {error}"))?;

    let mut response_line = String::new();
    let bytes_read = process
        .stdout
        .read_line(&mut response_line)
        .map_err(|error| format!("Failed to read Python worker response: {error}"))?;

    if bytes_read == 0 || response_line.trim().is_empty() {
        return Err("Python worker returned no JSON response".to_string());
    }

    let response: Value = serde_json::from_str(response_line.trim())
        .map_err(|error| format!("Python worker returned invalid JSON: {error}"))?;

    let response_id = response.get("id").and_then(Value::as_str).unwrap_or("");
    if response_id != request_id {
        return Err(format!(
            "Python worker response id mismatch: expected {request_id}, got {response_id}"
        ));
    }

    if response.get("ok").and_then(Value::as_bool) == Some(true) {
        return Ok(response.get("data").cloned().unwrap_or(Value::Null));
    }

    Err(response
        .get("message")
        .and_then(Value::as_str)
        .unwrap_or("Python worker command failed")
        .to_string())
}

#[tauri::command]
fn detect_playlist(state: State<'_, WorkerState>, url: String) -> Result<Value, String> {
    call_python_worker(state.inner(), "detect", json!({ "url": url }))
}

#[tauri::command]
fn preview_playlist(state: State<'_, WorkerState>, url: String) -> Result<Value, String> {
    call_python_worker(state.inner(), "preview", json!({ "url": url }))
}

#[tauri::command]
fn add_playlist(
    state: State<'_, WorkerState>,
    url: String,
    folder: String,
) -> Result<Value, String> {
    call_python_worker(state.inner(), "add", json!({ "url": url, "folder": folder }))
}

#[tauri::command]
fn list_playlists(state: State<'_, WorkerState>) -> Result<Value, String> {
    call_python_worker(state.inner(), "list", json!({}))
}

#[tauri::command]
fn get_playlist_details(
    state: State<'_, WorkerState>,
    playlist_id: String,
) -> Result<Value, String> {
    call_python_worker(
        state.inner(),
        "playlist_details",
        json!({ "playlist_id": playlist_id }),
    )
}

#[tauri::command]
fn sync_playlist(state: State<'_, WorkerState>, playlist_id: String) -> Result<Value, String> {
    call_python_worker(state.inner(), "sync", json!({ "playlist_id": playlist_id }))
}

#[tauri::command]
fn download_missing(state: State<'_, WorkerState>, playlist_id: String) -> Result<Value, String> {
    call_python_worker(
        state.inner(),
        "download_missing",
        json!({ "playlist_id": playlist_id }),
    )
}

#[tauri::command]
fn delete_playlist(state: State<'_, WorkerState>, playlist_id: String) -> Result<Value, String> {
    call_python_worker(
        state.inner(),
        "delete_playlist",
        json!({ "playlist_id": playlist_id }),
    )
}

#[tauri::command]
fn cancel_playlist_sync(
    state: State<'_, WorkerState>,
    playlist_id: String,
) -> Result<Value, String> {
    call_python_worker(
        state.inner(),
        "cancel_playlist_sync",
        json!({ "playlist_id": playlist_id }),
    )
}

#[tauri::command]
fn get_sync_status(state: State<'_, WorkerState>, playlist_id: String) -> Result<Value, String> {
    call_python_worker(
        state.inner(),
        "sync_status",
        json!({ "playlist_id": playlist_id }),
    )
}

#[tauri::command]
fn sync_all_playlists(state: State<'_, WorkerState>) -> Result<Value, String> {
    call_python_worker(state.inner(), "sync_all", json!({}))
}

#[tauri::command]
fn get_sync_all_status(state: State<'_, WorkerState>) -> Result<Value, String> {
    call_python_worker(state.inner(), "sync_all_status", json!({}))
}

#[tauri::command]
fn get_sync_tasks_status(state: State<'_, WorkerState>) -> Result<Value, String> {
    call_python_worker(state.inner(), "sync_tasks_status", json!({}))
}

#[tauri::command]
fn cancel_sync_all(state: State<'_, WorkerState>) -> Result<Value, String> {
    call_python_worker(state.inner(), "cancel_sync_all", json!({}))
}

fn open_target(target: &str) -> Result<(), String> {
    if target.trim().is_empty() {
        return Err("No target provided.".to_string());
    }

    let status = if cfg!(target_os = "macos") {
        Command::new("open").arg(target).status()
    } else if cfg!(windows) {
        Command::new("cmd").args(["/C", "start", "", target]).status()
    } else {
        Command::new("xdg-open").arg(target).status()
    }
    .map_err(|error| format!("Failed to open target: {error}"))?;

    if status.success() {
        Ok(())
    } else {
        Err("Open command failed".to_string())
    }
}

fn playlist_folder_from_path(path: &str) -> Result<PathBuf, String> {
    let trimmed = path.trim();

    if trimmed.is_empty() {
        return Err("No folder path provided.".to_string());
    }

    let input_path = PathBuf::from(trimmed);
    let mut folder = if input_path.is_dir() {
        input_path
    } else if let Some(parent) = input_path.parent() {
        parent.to_path_buf()
    } else {
        return Err("Invalid folder path.".to_string());
    };

    if folder.file_name().and_then(|name| name.to_str()) == Some(".yousync") {
        if let Some(parent) = folder.parent() {
            folder = parent.to_path_buf();
        }
    }

    if !folder.exists() {
        return Err("Folder does not exist.".to_string());
    }

    if !folder.is_dir() {
        return Err("Target is not a folder.".to_string());
    }

    Ok(folder)
}

#[tauri::command]
fn open_playlist_folder(path: String) -> Result<(), String> {
    let folder = playlist_folder_from_path(&path)?;
    open_target(&folder.to_string_lossy())
}

#[tauri::command]
fn open_external_url(url: String) -> Result<(), String> {
    open_target(&url)
}

#[tauri::command]
fn open_local_file(path: String) -> Result<(), String> {
    let file_path = PathBuf::from(path.trim());

    if !file_path.is_file() {
        return Err("Local file does not exist.".to_string());
    }

    open_target(&file_path.to_string_lossy())
}

#[tauri::command]
fn open_folder(path: String) -> Result<(), String> {
    open_playlist_folder(path)
}

#[tauri::command]
fn open_url(url: String) -> Result<(), String> {
    open_external_url(url)
}

#[tauri::command]
fn redownload_track(
    state: State<'_, WorkerState>,
    playlist_id: String,
    track_index: u64,
) -> Result<Value, String> {
    call_python_worker(
        state.inner(),
        "redownload_track",
        json!({ "playlist_id": playlist_id, "track_index": track_index }),
    )
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(WorkerState::new().expect("failed to start Python worker"))
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            detect_playlist,
            preview_playlist,
            add_playlist,
            list_playlists,
            get_playlist_details,
            sync_playlist,
            download_missing,
            delete_playlist,
            cancel_playlist_sync,
            get_sync_status,
            sync_all_playlists,
            get_sync_all_status,
            get_sync_tasks_status,
            cancel_sync_all,
            redownload_track,
            open_playlist_folder,
            open_external_url,
            open_local_file,
            open_folder,
            open_url
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
