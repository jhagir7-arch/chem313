//! Chem313 desktop host.
//!
//! Starts the frozen Python engine (`chem313-engine`) as a child process on a random loopback
//! port, holds its session token, and proxies the webview's API calls to it. The webview never
//! learns the token, so the engine's origin checks stay strict and no CORS rule is
//! needed. The engine is killed when the app exits.

use serde::Serialize;
use std::io::{BufRead, BufReader, Read};
use std::time::Duration;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem, Submenu};
use tauri::{AppHandle, Emitter, Manager, RunEvent, State};
use tauri_plugin_dialog::DialogExt;

#[derive(Default)]
struct Engine {
    child: Option<Child>,
    url: Option<String>,
    token: Option<String>,
    error: Option<String>,
    data_dir: String,
}

type EngineState = Mutex<Engine>;

#[derive(Serialize, Clone)]
struct EngineStatus {
    ready: bool,
    url: Option<String>,
    error: Option<String>,
    data_dir: String,
}

#[derive(Serialize)]
struct Proxied {
    status: u16,
    body: String,
}

/// Where the engine executable lives: `CHEM313_ENGINE` for development, else the bundled resource.
fn engine_executable(app: &AppHandle) -> Result<PathBuf, String> {
    if let Ok(path) = std::env::var("CHEM313_ENGINE") {
        let path = PathBuf::from(path);
        if path.is_file() {
            return Ok(path);
        }
        return Err(format!("CHEM313_ENGINE is not a file: {}", path.display()));
    }
    let resources = app.path().resource_dir().map_err(|e| e.to_string())?;
    let name = if cfg!(windows) { "chem313-engine.exe" } else { "chem313-engine" };
    let path = resources.join("engine").join(name);
    if path.is_file() {
        Ok(path)
    } else {
        Err(format!("Engine not found at {}. Set CHEM313_ENGINE for development.", path.display()))
    }
}

/// Read a bounded startup banner without allowing a broken child to block startup indefinitely.
fn read_banner<R: Read + Send + 'static>(stdout: R, timeout: Duration) -> Result<String, String> {
    let (tx, rx) = std::sync::mpsc::channel();
    std::thread::spawn(move || {
        let mut line = String::new();
        let result = BufReader::new(stdout.take(8192)).read_line(&mut line)
            .map(|_| line).map_err(|e| format!("Cannot read engine banner: {e}"));
        let _ = tx.send(result);
    });
    let line = rx.recv_timeout(timeout).map_err(|e| format!("Engine startup banner unavailable: {e}"))??;
    if !line.ends_with('\n') { return Err("Incomplete engine banner".into()); }
    let banner: serde_json::Value = serde_json::from_str(line.trim())
        .map_err(|e| format!("Bad engine banner: {e}"))?;
    let url = banner["url"].as_str().ok_or("Engine banner has no url")?;
    let parsed = reqwest::Url::parse(url).map_err(|e| format!("Invalid engine URL: {e}"))?;
    if parsed.scheme() != "http" || parsed.host_str() != Some("127.0.0.1") || parsed.port().is_none()
        || parsed.path() != "/" || parsed.query().is_some() || parsed.fragment().is_some()
        || !parsed.username().is_empty() || parsed.password().is_some() {
        return Err("Engine banner URL must be a loopback HTTP origin with a port".into());
    }
    Ok(url.to_string())
}

/// Spawn the engine and wait at most 30 seconds for its one-line JSON banner.
fn start_engine(app: &AppHandle) -> Result<(Child, String), String> {
    let exe = engine_executable(app)?;
    let data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;
    let mut child = Command::new(&exe)
        .arg("--data").arg(&data_dir).arg("--port").arg("0")
        .arg("--parent-pid").arg(std::process::id().to_string())
        .stdout(Stdio::piped()).stderr(Stdio::inherit())
        .spawn().map_err(|e| format!("Cannot start {}: {e}", exe.display()))?;
    let result = match child.stdout.take() {
        Some(stdout) => read_banner(stdout, Duration::from_secs(30)),
        None => Err("Engine produced no stdout".into()),
    };
    match result {
        Ok(url) => Ok((child, url)),
        Err(error) => {
            let _ = child.kill();
            let _ = child.wait();
            Err(error)
        }
    }
}

fn stop_engine(state: &EngineState) {
    if let Ok(mut engine) = state.lock() {
        if let Some(mut child) = engine.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

#[tauri::command]
fn engine_status(state: State<'_, EngineState>) -> EngineStatus {
    let mut engine = state.lock().unwrap();
    let exited = match engine.child.as_mut() {
        Some(child) => match child.try_wait() {
            Ok(Some(status)) => Some(format!("Engine exited: {status}")),
            Err(error) => Some(format!("Cannot check engine process: {error}")),
            Ok(None) => None,
        },
        None => None,
    };
    if let Some(error) = exited {
        engine.url = None;
        engine.token = None;
        engine.error = Some(error);
    }
    EngineStatus { ready: engine.url.is_some() && engine.child.is_some(), url: engine.url.clone(), error: engine.error.clone(), data_dir: engine.data_dir.clone() }
}

/// The webview may only reach the engine's API: absolute, under /api/, no traversal, no scheme tricks.
fn proxied_path_ok(path: &str) -> bool {
    path.starts_with("/api/") && !path.contains("..") && !path.contains("//") && !path.contains('\\') && !path.contains('\n') && path.len() < 2048
}

#[tauri::command]
async fn engine_request(state: State<'_, EngineState>, method: String, path: String, body: Option<String>) -> Result<Proxied, String> {
    if !proxied_path_ok(&path) {
        return Err("Only /api/ paths are proxied".into());
    }
    let (url, token) = {
        let engine = state.lock().unwrap();
        (engine.url.clone().ok_or("Engine is not running")?, engine.token.clone())
    };
    let client = reqwest::Client::new();
    let token = match token {
        Some(t) => t,
        None => {
            let session: serde_json::Value = client.get(format!("{url}/api/session")).send().await.map_err(|e| e.to_string())?.json().await.map_err(|e| e.to_string())?;
            let t = session["session_token"].as_str().ok_or("Engine session has no token")?.to_string();
            state.lock().unwrap().token = Some(t.clone());
            t
        }
    };
    let mut request = match method.as_str() {
        "GET" => client.get(format!("{url}{path}")),
        "POST" => client.post(format!("{url}{path}")),
        other => return Err(format!("Unsupported method {other}")),
    }
    .header("X-HypothesisLab-Session", token);
    if let Some(body) = body {
        request = request.header("Content-Type", "application/json").body(body);
    }
    let response = request.send().await.map_err(|e| e.to_string())?;
    let status = response.status().as_u16();
    let body = response.text().await.map_err(|e| e.to_string())?;
    if std::env::var_os("CHEM313_DEBUG").is_some() {
        eprintln!("[chem313] {method} {path} -> {status} {}", body.chars().take(200).collect::<String>());
    }
    Ok(Proxied { status, body })
}

/// Native save dialog for a text record; `None` when the user cancels.
#[tauri::command]
async fn save_text_file(app: AppHandle, suggested_name: String, contents: String) -> Result<Option<String>, String> {
    let safe = suggested_name.chars().filter(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.')).collect::<String>();
    let Some(path) = app.dialog().file().set_file_name(if safe.is_empty() { "record.json" } else { &safe }).add_filter("JSON", &["json"]).blocking_save_file() else {
        return Ok(None);
    };
    let path = path.into_path().map_err(|e| e.to_string())?;
    std::fs::write(&path, contents).map_err(|e| format!("Cannot write {}: {e}", path.display()))?;
    Ok(Some(path.display().to_string()))
}

#[derive(Serialize)]
struct OpenedFile {
    name: String,
    contents: String,
}

/// Native open dialog for a .mol/.sdf structure; the file is read here and handed to the webview as text.
#[tauri::command]
async fn open_structure_file(app: AppHandle) -> Result<Option<OpenedFile>, String> {
    let Some(path) = app.dialog().file().add_filter("Structure", &["mol", "sdf"]).blocking_pick_file() else {
        return Ok(None);
    };
    let path = path.into_path().map_err(|e| e.to_string())?;
    let metadata = std::fs::metadata(&path).map_err(|e| e.to_string())?;
    if metadata.len() > 250_000 {
        return Err("Structure files up to 250 KB are supported".into());
    }
    let contents = std::fs::read_to_string(&path).map_err(|e| format!("Cannot read {}: {e}", path.display()))?;
    let name = path.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_else(|| "structure".into());
    Ok(Some(OpenedFile { name, contents }))
}

/// Interface errors are forwarded here so they show up in the host's stderr (and in CI logs).
#[tauri::command]
fn log_message(level: String, message: String) {
    eprintln!("[chem313 ui:{level}] {}", message.chars().take(2000).collect::<String>());
}

fn build_menu(app: &AppHandle) -> tauri::Result<Menu<tauri::Wry>> {
    let item = |id: &str, label: &str, accel: Option<&str>| MenuItem::with_id(app, id, label, true, accel);
    let file = Submenu::with_items(
        app,
        "File",
        true,
        &[
            &item("new-molecule", "New Molecule", Some("CmdOrCtrl+N"))?,
            &item("import", "Import Structure…", Some("CmdOrCtrl+O"))?,
            &PredefinedMenuItem::separator(app)?,
            &item("export-record", "Export Record…", Some("CmdOrCtrl+E"))?,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::close_window(app, None)?,
            #[cfg(not(target_os = "macos"))]
            &PredefinedMenuItem::quit(app, None)?,
        ],
    )?;
    let edit = Submenu::with_items(
        app,
        "Edit",
        true,
        &[
            &PredefinedMenuItem::undo(app, None)?,
            &PredefinedMenuItem::redo(app, None)?,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::cut(app, None)?,
            &PredefinedMenuItem::copy(app, None)?,
            &PredefinedMenuItem::paste(app, None)?,
            &PredefinedMenuItem::select_all(app, None)?,
        ],
    )?;
    let view = Submenu::with_items(
        app,
        "View",
        true,
        &[
            &item("tab-structure", "Structure", Some("CmdOrCtrl+1"))?,
            &item("tab-3d", "3D", Some("CmdOrCtrl+2"))?,
            &item("tab-setup", "Setup", Some("CmdOrCtrl+3"))?,
            &item("tab-results", "Results", Some("CmdOrCtrl+4"))?,
            &PredefinedMenuItem::separator(app)?,
            &item("toggle-navigator", "Toggle Navigator", Some("CmdOrCtrl+Alt+1"))?,
            &item("toggle-inspector", "Toggle Inspector", Some("CmdOrCtrl+Alt+2"))?,
            &item("toggle-console", "Toggle Console", Some("CmdOrCtrl+Alt+3"))?,
            &PredefinedMenuItem::separator(app)?,
            &item("toggle-guided", "Guided Mode", Some("CmdOrCtrl+G"))?,
            &item("command-palette", "Command Palette…", Some("CmdOrCtrl+K"))?,
            #[cfg(target_os = "macos")]
            &PredefinedMenuItem::separator(app)?,
            #[cfg(target_os = "macos")]
            &PredefinedMenuItem::fullscreen(app, None)?,
        ],
    )?;
    let calculation = Submenu::with_items(
        app,
        "Calculation",
        true,
        &[
            &item("check", "Check Structure", Some("CmdOrCtrl+Shift+C"))?,
            &item("run", "Run", Some("CmdOrCtrl+R"))?,
        ],
    )?;
    let window = Submenu::with_items(
        app,
        "Window",
        true,
        &[&PredefinedMenuItem::minimize(app, None)?, &PredefinedMenuItem::maximize(app, None)?, &PredefinedMenuItem::separator(app)?, &PredefinedMenuItem::close_window(app, None)?],
    )?;
    let help = Submenu::with_items(app, "Help", true, &[&item("help-scope", "Scientific Scope", None)?, &item("help-issues", "Report an Issue…", None)?])?;

    #[cfg(target_os = "macos")]
    {
        let app_menu = Submenu::with_items(
            app,
            "Chem313",
            true,
            &[
                &PredefinedMenuItem::about(app, None, None)?,
                &PredefinedMenuItem::separator(app)?,
                &item("preferences", "Settings…", Some("CmdOrCtrl+,"))?,
                &PredefinedMenuItem::separator(app)?,
                &PredefinedMenuItem::services(app, None)?,
                &PredefinedMenuItem::separator(app)?,
                &PredefinedMenuItem::hide(app, None)?,
                &PredefinedMenuItem::hide_others(app, None)?,
                &PredefinedMenuItem::separator(app)?,
                &PredefinedMenuItem::quit(app, None)?,
            ],
        )?;
        return Menu::with_items(app, &[&app_menu, &file, &edit, &view, &calculation, &window, &help]);
    }
    #[cfg(not(target_os = "macos"))]
    Menu::with_items(app, &[&file, &edit, &view, &calculation, &window, &help])
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(EngineState::default())
        .menu(|handle| build_menu(handle))
        .on_menu_event(|app, event| {
            // Every custom item is forwarded to the webview as a plain string id.
            let _ = app.emit("menu", event.id().0.clone());
        })
        .setup(|app| {
            let handle = app.handle().clone();
            let state = app.state::<EngineState>();
            let mut engine = state.lock().unwrap();
            engine.data_dir = app.path().app_data_dir().map(|p| p.display().to_string()).unwrap_or_default();
            match start_engine(&handle) {
                Ok((child, url)) => {
                    engine.child = Some(child);
                    engine.url = Some(url);
                }
                Err(message) => {
                    eprintln!("[chem313] engine failed to start: {message}");
                    engine.error = Some(message);
                }
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![engine_status, engine_request, save_text_file, open_structure_file, log_message])
        .build(tauri::generate_context!())
        .expect("error while building Chem313")
        .run(|app, event| {
            // Quit from the menu raises ExitRequested first; a plain exit raises only Exit. Stop on either.
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                stop_engine(&app.state::<EngineState>());
            }
        });
}


#[cfg(test)]
mod tests {
    use super::{proxied_path_ok, read_banner};
    use std::io::{Cursor, Read};
    use std::time::Duration;

    #[test]
    fn banner_validation_and_timeout() {
        assert_eq!(read_banner(Cursor::new(b"{\"url\":\"http://127.0.0.1:1234\"}\n"), Duration::from_secs(1)).unwrap(), "http://127.0.0.1:1234");
        assert!(read_banner(Cursor::new(b"invalid\n"), Duration::from_secs(1)).is_err());
        assert!(read_banner(Cursor::new(b"{\"url\":\"http://example.com:1234\"}\n"), Duration::from_secs(1)).is_err());
        assert!(read_banner(Cursor::new(b"{}"), Duration::from_secs(1)).is_err());
        struct Slow;
        impl Read for Slow {
            fn read(&mut self, _: &mut [u8]) -> std::io::Result<usize> {
                std::thread::sleep(Duration::from_millis(100));
                Ok(0)
            }
        }
        assert!(read_banner(Slow, Duration::from_millis(10)).is_err());
    }


    #[test]
    fn only_api_paths_are_proxied() {
        assert!(proxied_path_ok("/api/workbench"));
        assert!(proxied_path_ok("/api/projects/default/artifact/reports/abc.json"));
        assert!(!proxied_path_ok("/openapi.json"));
        assert!(!proxied_path_ok("api/workbench"));
        assert!(!proxied_path_ok("/api/../etc/passwd"));
        assert!(!proxied_path_ok("/api//double"));
        assert!(!proxied_path_ok("/api/x\nHost: evil"));
        assert!(!proxied_path_ok(&format!("/api/{}", "a".repeat(3000))));
    }
}
