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
fn sync_playlist(state: State<'_, WorkerState>, playlist_id: String) -> Result<Value, String> {
    call_python_worker(state.inner(), "sync", json!({ "playlist_id": playlist_id }))
}

#[tauri::command]
fn get_sync_status(state: State<'_, WorkerState>, playlist_id: String) -> Result<Value, String> {
    call_python_worker(
        state.inner(),
        "sync_status",
        json!({ "playlist_id": playlist_id }),
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
            sync_playlist,
            get_sync_status
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
