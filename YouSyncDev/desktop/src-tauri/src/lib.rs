use serde_json::{json, Value};
use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use tauri::{AppHandle, Manager, State};

const WORKER_SIDECAR_NAME: &str = "yousync-worker";

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

fn worker_script_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../python/yousync_worker.py")
}

enum WorkerLaunch {
    Python { python: PathBuf, script: PathBuf },
    Sidecar { path: PathBuf },
}

fn sidecar_candidates(app_handle: &AppHandle) -> Vec<PathBuf> {
    let mut candidates = Vec::new();

    if let Ok(resource_dir) = app_handle.path().resource_dir() {
        candidates.push(resource_dir.join(WORKER_SIDECAR_NAME));
    }

    if let Ok(current_exe) = std::env::current_exe() {
        if let Some(exe_dir) = current_exe.parent() {
            candidates.push(exe_dir.join(WORKER_SIDECAR_NAME));

            #[cfg(target_os = "macos")]
            if let Some(contents_dir) = exe_dir.parent() {
                candidates.push(contents_dir.join("Resources").join(WORKER_SIDECAR_NAME));
            }
        }
    }

    candidates
}

fn packaged_worker_sidecar(app_handle: &AppHandle) -> Option<PathBuf> {
    sidecar_candidates(app_handle)
        .into_iter()
        .find(|path| path.is_file())
}

fn worker_launch(app_handle: &AppHandle) -> Result<WorkerLaunch, String> {
    let script = worker_script_path();

    if cfg!(debug_assertions) && script.is_file() {
        return Ok(WorkerLaunch::Python {
            python: python_executable(),
            script,
        });
    }

    if let Some(path) = packaged_worker_sidecar(app_handle) {
        return Ok(WorkerLaunch::Sidecar { path });
    }

    if script.is_file() {
        return Ok(WorkerLaunch::Python {
            python: python_executable(),
            script,
        });
    }

    Err(format!(
        "Could not find YouSync worker sidecar '{}' or source worker '{}'.",
        WORKER_SIDECAR_NAME,
        script.display()
    ))
}

struct WorkerProcess {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

fn user_home_dir() -> Option<PathBuf> {
    std::env::var_os("HOME")
        .map(PathBuf::from)
        .filter(|path| !path.as_os_str().is_empty())
}

fn logs_folder_path() -> Result<PathBuf, String> {
    if cfg!(target_os = "macos") {
        return user_home_dir()
            .map(|home| home.join("Library").join("Logs").join("YouSync"))
            .ok_or_else(|| "Could not resolve the user home folder.".to_string());
    }

    if cfg!(windows) {
        if let Some(local_app_data) = std::env::var_os("LOCALAPPDATA") {
            return Ok(PathBuf::from(local_app_data).join("YouSync").join("logs"));
        }

        if let Some(app_data) = std::env::var_os("APPDATA") {
            return Ok(PathBuf::from(app_data).join("YouSync").join("logs"));
        }

        return user_home_dir()
            .map(|home| home.join("AppData").join("Local").join("YouSync").join("logs"))
            .ok_or_else(|| "Could not resolve a logs folder.".to_string());
    }

    if let Some(xdg_state_home) = std::env::var_os("XDG_STATE_HOME") {
        return Ok(PathBuf::from(xdg_state_home).join("yousync").join("logs"));
    }

    user_home_dir()
        .map(|home| home.join(".local").join("state").join("yousync").join("logs"))
        .ok_or_else(|| "Could not resolve a logs folder.".to_string())
}

fn write_logs_info_file(logs_dir: &Path) -> Result<(), String> {
    let readme_dir = logs_dir.join("README");
    fs::create_dir_all(&readme_dir)
        .map_err(|error| format!("Failed to create logs README folder: {error}"))?;

    let info_path = readme_dir.join("logs-info.txt");

    if info_path.is_file() {
        return Ok(());
    }

    let content = [
        "YouSync logs",
        "",
        "Persistent application and worker logs are stored in this folder.",
        "",
        "Temporary runtime/progress job files are stored separately in:",
        "/tmp/yousync_jobs",
        "",
        "You can delete temporary job files when YouSync is not running.",
        "",
    ]
    .join("\n");

    fs::write(&info_path, content)
        .map_err(|error| format!("Failed to write logs info file: {error}"))
}

fn ensure_logs_folder() -> Result<PathBuf, String> {
    let logs_dir = logs_folder_path()?;

    fs::create_dir_all(&logs_dir)
        .map_err(|error| format!("Failed to create logs folder: {error}"))?;
    write_logs_info_file(&logs_dir)?;

    Ok(logs_dir)
}

fn prepare_worker_logs() -> (Option<PathBuf>, Stdio) {
    match ensure_logs_folder() {
        Ok(logs_dir) => {
            let log_path = logs_dir.join("yousync-worker.log");
            match OpenOptions::new().create(true).append(true).open(&log_path) {
                Ok(file) => (Some(logs_dir), Stdio::from(file)),
                Err(error) => {
                    eprintln!("[YouSync] Failed to open worker log file: {error}");
                    (Some(logs_dir), Stdio::inherit())
                }
            }
        }
        Err(error) => {
            eprintln!("[YouSync] Failed to prepare logs folder: {error}");
            (None, Stdio::inherit())
        }
    }
}

impl WorkerProcess {
    fn new(app_handle: &AppHandle) -> Result<Self, String> {
        let launch = worker_launch(app_handle)?;
        let mut command = match &launch {
            WorkerLaunch::Python { python, script } => {
                let mut command = Command::new(python);
                command.arg("-u").arg(script);
                command
            }
            WorkerLaunch::Sidecar { path } => Command::new(path),
        };
        let (logs_dir, worker_stderr) = prepare_worker_logs();

        if let Some(logs_dir) = logs_dir {
            command.env("YOUSYNC_LOGS_DIR", logs_dir.as_os_str());
        }

        let mut child = command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(worker_stderr)
            .spawn()
            .map_err(|error| match launch {
                WorkerLaunch::Python { python, .. } => {
                    format!(
                        "Failed to start Python worker with '{}': {error}",
                        python.display()
                    )
                }
                WorkerLaunch::Sidecar { path } => {
                    format!(
                        "Failed to start YouSync worker sidecar '{}': {error}",
                        path.display()
                    )
                }
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
    fn new(app_handle: AppHandle) -> Result<Self, String> {
        Ok(Self {
            process: Mutex::new(WorkerProcess::new(&app_handle)?),
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
fn list_missing_playlists(state: State<'_, WorkerState>) -> Result<Value, String> {
    call_python_worker(state.inner(), "list_missing_playlists", json!({}))
}

#[tauri::command]
fn update_playlist_folder(
    state: State<'_, WorkerState>,
    playlist_id: String,
    folder: String,
) -> Result<Value, String> {
    call_python_worker(
        state.inner(),
        "update_playlist_folder",
        json!({ "playlist_id": playlist_id, "folder": folder }),
    )
}

#[tauri::command]
fn recover_existing_playlist(
    state: State<'_, WorkerState>,
    folder: String,
) -> Result<Value, String> {
    call_python_worker(
        state.inner(),
        "recover_existing_playlist",
        json!({ "folder": folder }),
    )
}

#[tauri::command]
fn move_playlist_folder(
    state: State<'_, WorkerState>,
    playlist_id: String,
    folder: String,
) -> Result<Value, String> {
    call_python_worker(
        state.inner(),
        "move_playlist_folder",
        json!({ "playlist_id": playlist_id, "folder": folder }),
    )
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
fn delete_playlist(
    state: State<'_, WorkerState>,
    playlist_id: String,
    delete_local_files: Option<bool>,
) -> Result<Value, String> {
    call_python_worker(
        state.inner(),
        "delete_playlist",
        json!({ "playlist_id": playlist_id, "delete_local_files": delete_local_files.unwrap_or(false) }),
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
fn open_playlists_json() -> Result<(), String> {
    let project_root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let playlists_json = project_root.join("core/playlists.json");

    if playlists_json.is_file() {
        return open_target(&playlists_json.to_string_lossy());
    }

    let core_folder = project_root.join("core");

    if core_folder.is_dir() {
        return open_target(&core_folder.to_string_lossy());
    }

    Err("playlists.json could not be found.".to_string())
}

#[tauri::command]
fn open_logs_folder() -> Result<String, String> {
    let logs_dir = ensure_logs_folder()?;
    open_target(&logs_dir.to_string_lossy())?;
    Ok(logs_dir.to_string_lossy().into_owned())
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
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let worker_state = WorkerState::new(app.handle().clone()).map_err(|error| {
                Box::<dyn std::error::Error>::from(std::io::Error::new(
                    std::io::ErrorKind::Other,
                    error,
                ))
            })?;
            app.manage(worker_state);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            detect_playlist,
            preview_playlist,
            add_playlist,
            list_playlists,
            list_missing_playlists,
            update_playlist_folder,
            recover_existing_playlist,
            move_playlist_folder,
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
            open_playlists_json,
            open_logs_folder,
            open_folder,
            open_url
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
