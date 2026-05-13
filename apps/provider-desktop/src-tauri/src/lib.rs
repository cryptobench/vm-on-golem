use serde::Serialize;
use std::net::{SocketAddr, TcpStream};
use std::time::Duration;
use tauri_plugin_shell::ShellExt;

const PROVIDER_HOST: &str = "127.0.0.1";
const PROVIDER_PORT: u16 = 7466;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct ProviderStatus {
    running: bool,
    api_base_url: String,
}

fn provider_api_base_url_value() -> String {
    format!("http://{PROVIDER_HOST}:{PROVIDER_PORT}/api/v1")
}

fn provider_is_listening() -> bool {
    let addr = SocketAddr::from(([127, 0, 0, 1], PROVIDER_PORT));
    TcpStream::connect_timeout(&addr, Duration::from_millis(300)).is_ok()
}

async fn run_provider_sidecar(app: tauri::AppHandle, args: &[&str]) -> Result<(), String> {
    let output = app
        .shell()
        .sidecar("golem-provider")
        .map_err(|err| err.to_string())?
        .args(args)
        .output()
        .await
        .map_err(|err| err.to_string())?;

    if output.status.success() {
        return Ok(());
    }

    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    Err(if stderr.is_empty() { stdout } else { stderr })
}

#[tauri::command]
async fn start_provider(app: tauri::AppHandle) -> Result<(), String> {
    run_provider_sidecar(app, &["start", "--daemon", "--no-verify-port"]).await
}

#[tauri::command]
async fn stop_provider(app: tauri::AppHandle) -> Result<(), String> {
    run_provider_sidecar(app, &["stop"]).await
}

#[tauri::command]
fn provider_status() -> ProviderStatus {
    ProviderStatus {
        running: provider_is_listening(),
        api_base_url: provider_api_base_url_value(),
    }
}

#[tauri::command]
fn provider_api_base_url() -> String {
    provider_api_base_url_value()
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            start_provider,
            stop_provider,
            provider_status,
            provider_api_base_url
        ])
        .run(tauri::generate_context!())
        .expect("failed to run Golem Provider desktop app");
}
