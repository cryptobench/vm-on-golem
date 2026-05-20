use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::fs::{self, File};
use std::io::{Read, Seek, SeekFrom, Write};
use std::net::{SocketAddr, TcpStream};
#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use std::time::{Duration, Instant};
use tauri::Emitter;
use tauri_plugin_shell::process::{Command, CommandEvent};
use tauri_plugin_shell::ShellExt;

const PROVIDER_HOST: &str = "127.0.0.1";
const PROVIDER_PORT: u16 = 7466;
const PROVIDER_START_TIMEOUT: Duration = Duration::from_secs(180);
const PAYMENTS_NETWORK: &str = "hoodi";
const PAYMENTS_RPC_URL: &str = "https://rpc.hoodi.ethpandaops.io";
const PAYMENTS_WS_URL: &str = "wss://ethereum-hoodi-rpc.publicnode.com";
const STREAM_PAYMENT_ADDRESS: &str = "0x479044F8A58276DC15d0d924a6A92Ec663877D00";
const GLM_TOKEN_ADDRESS: &str = "0x55555555555556AcFf9C332Ed151758858bd7a26";

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct ProviderStatus {
    running: bool,
    api_base_url: String,
    admin_authenticated: bool,
    admin_auth_error: Option<String>,
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all(serialize = "camelCase", deserialize = "snake_case"))]
struct ProviderRequirements {
    installed: bool,
    path: Option<String>,
    version: Option<String>,
    source: Option<String>,
    compatible: bool,
    daemon_running: bool,
    driver: Option<String>,
    action_required: String,
    error: Option<String>,
}

fn provider_api_base_url_value() -> String {
    format!("http://{PROVIDER_HOST}:{PROVIDER_PORT}/api/v1")
}

fn provider_vm_data_dir() -> Result<PathBuf, String> {
    if let Ok(value) = std::env::var("GOLEM_PROVIDER_VM_DATA_DIR") {
        let trimmed = value.trim();
        if !trimmed.is_empty() {
            let path = PathBuf::from(trimmed);
            return Ok(if path.is_absolute() {
                path
            } else {
                provider_home_dir()?.join(path)
            });
        }
    }
    Ok(provider_home_dir()?.join(".golem/provider/vms"))
}

fn env_or_default(key: &str, default: &str) -> String {
    std::env::var(key)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| default.to_string())
}

fn provider_sidecar_command(app: &tauri::AppHandle) -> Result<Command, String> {
    let admin_token = read_or_create_admin_token()?;
    let vm_data_dir = provider_vm_data_dir()?.to_string_lossy().to_string();
    app.shell()
        .sidecar("golem-provider")
        .map_err(|err| err.to_string())
        .map(|command| {
            command.envs([
                ("GOLEM_PROVIDER_ADMIN_TOKEN", admin_token),
                ("GOLEM_PROVIDER_VM_DATA_DIR", vm_data_dir),
                (
                    "GOLEM_PROVIDER_PAYMENTS_NETWORK",
                    env_or_default("GOLEM_PROVIDER_PAYMENTS_NETWORK", PAYMENTS_NETWORK),
                ),
                (
                    "GOLEM_PROVIDER_PAYMENTS_RPC_URL",
                    env_or_default("GOLEM_PROVIDER_PAYMENTS_RPC_URL", PAYMENTS_RPC_URL),
                ),
                (
                    "GOLEM_PROVIDER_PAYMENTS_WS_URL",
                    env_or_default("GOLEM_PROVIDER_PAYMENTS_WS_URL", PAYMENTS_WS_URL),
                ),
                (
                    "GOLEM_PROVIDER_STREAM_PAYMENT_ADDRESS",
                    env_or_default(
                        "GOLEM_PROVIDER_STREAM_PAYMENT_ADDRESS",
                        STREAM_PAYMENT_ADDRESS,
                    ),
                ),
                (
                    "GOLEM_PROVIDER_GLM_TOKEN_ADDRESS",
                    env_or_default("GOLEM_PROVIDER_GLM_TOKEN_ADDRESS", GLM_TOKEN_ADDRESS),
                ),
            ])
        })
}

fn provider_home_dir() -> Result<PathBuf, String> {
    std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .map(PathBuf::from)
        .map_err(|_| "Could not determine provider home directory".to_string())
}

fn generate_admin_token() -> Result<String, String> {
    let mut bytes = [0_u8; 48];
    File::open("/dev/urandom")
        .map_err(|err| format!("Failed to open OS random source: {err}"))?
        .read_exact(&mut bytes)
        .map_err(|err| format!("Failed to read OS random source: {err}"))?;
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

fn read_or_create_admin_token() -> Result<String, String> {
    if let Ok(value) = std::env::var("GOLEM_PROVIDER_ADMIN_TOKEN") {
        let trimmed = value.trim();
        if !trimmed.is_empty() {
            return Ok(trimmed.to_string());
        }
    }

    let path = provider_vm_data_dir()?.join("provider-admin.token");
    if path.exists() {
        let value = fs::read_to_string(&path).map_err(|err| err.to_string())?;
        let trimmed = value.trim();
        if !trimmed.is_empty() {
            return Ok(trimmed.to_string());
        }
    }

    let token = generate_admin_token()?;
    let parent = path
        .parent()
        .ok_or_else(|| "Provider admin token path has no parent".to_string())?;
    fs::create_dir_all(parent).map_err(|err| err.to_string())?;
    fs::write(&path, &token).map_err(|err| err.to_string())?;
    #[cfg(unix)]
    fs::set_permissions(&path, fs::Permissions::from_mode(0o600)).map_err(|err| err.to_string())?;
    Ok(token)
}

fn emit_setup_status(app: &tauri::AppHandle, status: Value) {
    let _ = app.emit("provider://setup-status", status);
}

fn set_stage(status: &mut Value, name: &str, state: &str, detail: &str) {
    if let Some(stages) = status.get_mut("stages").and_then(Value::as_array_mut) {
        for stage in stages {
            if stage.get("name").and_then(Value::as_str) == Some(name) {
                stage["state"] = json!(state);
                stage["detail"] = json!(detail);
            }
        }
    }
}

fn parse_setup_status(stdout: &str) -> Option<Value> {
    let trimmed = stdout.trim();
    if trimmed.is_empty() {
        return None;
    }
    if let Ok(value) = serde_json::from_str::<Value>(trimmed) {
        return Some(value);
    }
    for (index, ch) in trimmed.char_indices() {
        if ch == '{' {
            let mut deserializer = serde_json::Deserializer::from_str(&trimmed[index..]);
            if let Ok(value) = Value::deserialize(&mut deserializer) {
                return Some(value);
            }
        }
    }
    None
}

fn merge_output(stdout: &str, stderr: &str) -> String {
    match (stdout.trim().is_empty(), stderr.trim().is_empty()) {
        (true, true) => String::new(),
        (true, false) => stderr.trim().to_string(),
        (false, true) => stdout.trim().to_string(),
        (false, false) => format!("{}\n{}", stdout.trim(), stderr.trim()),
    }
}

fn json_stream_unsupported(output: &str) -> bool {
    output.contains("No such option: --json-stream")
}

async fn run_secure_setup_once(app: tauri::AppHandle) -> Result<Value, String> {
    let setup =
        run_provider_sidecar_output(app.clone(), &["secure-setup", "check", "--json"]).await?;
    let stdout = String::from_utf8_lossy(&setup.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&setup.stderr).trim().to_string();
    let output = merge_output(&stdout, &stderr);

    if let Some(status) = parse_setup_status(&stdout).or_else(|| parse_setup_status(&output)) {
        emit_setup_status(&app, status.clone());
        if setup.status.success() {
            return Ok(status);
        }
        return Err(serde_json::to_string(&status).unwrap_or(output));
    }

    if setup.status.success() {
        return Err("Secure setup produced no status output".to_string());
    }
    Err(if output.is_empty() {
        "Secure setup failed".to_string()
    } else {
        output
    })
}

fn mark_provider_daemon_starting(status: &mut Value) {
    status["message"] = json!("Starting provider service.");
    set_stage(status, "provider_start", "running", "starting daemon");
}

fn mark_provider_daemon_started(status: &mut Value) {
    status["message"] = json!("Provider service started.");
    set_stage(status, "provider_start", "success", "API listening");
}

fn mark_provider_daemon_failed(status: &mut Value, detail: &str) {
    status["message"] = json!(detail);
    status["error"] = json!(detail);
    set_stage(status, "provider_start", "failed", detail);
}

fn setup_status_starting() -> Value {
    json!({
        "message": "Setting up SSL before the provider starts.",
        "api_http_public_port": 80,
        "api_https_public_port": 443,
        "vm_port_range_start": 50800,
        "vm_port_range_end": 50900,
        "stages": [
            {"name": "host_requirements", "state": "running", "label": "Checking host requirements", "detail": "starting Multipass checks"},
            {"name": "public_ip", "state": "pending", "label": "Public IP detected", "detail": ""},
            {"name": "network_access", "state": "pending", "label": "Ports 80 and 443 available", "detail": ""},
            {"name": "certificate", "state": "pending", "label": "Checking certificate", "detail": ""},
            {"name": "https_verification", "state": "pending", "label": "Secure endpoint verified", "detail": ""},
            {"name": "vm_port_range", "state": "pending", "label": "VM ports 50800-50900 reachable", "detail": ""},
            {"name": "provider_start", "state": "pending", "label": "Provider service started", "detail": ""}
        ]
    })
}

fn provider_is_listening() -> bool {
    let addr = SocketAddr::from(([127, 0, 0, 1], PROVIDER_PORT));
    TcpStream::connect_timeout(&addr, Duration::from_millis(300)).is_ok()
}

fn provider_admin_auth_status() -> (bool, Option<String>) {
    if !provider_is_listening() {
        return (false, None);
    }

    let token = match read_or_create_admin_token() {
        Ok(token) => token,
        Err(err) => return (false, Some(err)),
    };
    let addr = SocketAddr::from(([127, 0, 0, 1], PROVIDER_PORT));
    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(500)) {
        Ok(stream) => stream,
        Err(err) => return (false, Some(format!("Provider API unavailable: {err}"))),
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(700)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(700)));

    let request = format!(
        "GET /api/v1/provider/settings HTTP/1.1\r\n\
         Host: {PROVIDER_HOST}:{PROVIDER_PORT}\r\n\
         Accept: application/json\r\n\
         Authorization: Bearer {token}\r\n\
         Connection: close\r\n\r\n"
    );
    if let Err(err) = stream.write_all(request.as_bytes()) {
        return (
            false,
            Some(format!("Provider API auth check failed: {err}")),
        );
    }

    let mut response = String::new();
    if let Err(err) = stream.read_to_string(&mut response) {
        return (
            false,
            Some(format!("Provider API auth check failed: {err}")),
        );
    }
    let status_line = response.lines().next().unwrap_or_default().to_string();
    if status_line.contains(" 200 ") {
        return (true, None);
    }
    if status_line.contains(" 401 ") || status_line.contains(" 403 ") {
        return (
            false,
            Some("Provider admin token rejected by the running provider".to_string()),
        );
    }
    (
        false,
        Some(if status_line.is_empty() {
            "Provider API auth check returned an empty response".to_string()
        } else {
            format!("Provider API auth check returned {status_line}")
        }),
    )
}

fn daemon_stdio_log_path() -> Option<PathBuf> {
    std::env::var("GOLEM_PROVIDER_LOG_DIR")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .map(|value| PathBuf::from(value).join("provider-daemon-stdio.log"))
}

fn file_len(path: &Path) -> u64 {
    fs::metadata(path)
        .map(|metadata| metadata.len())
        .unwrap_or(0)
}

fn read_daemon_log_since(path: &Path, offset: u64) -> String {
    let Ok(mut file) = File::open(path) else {
        return String::new();
    };
    if file.seek(SeekFrom::Start(offset)).is_err() {
        return String::new();
    }
    let mut output = String::new();
    if file.read_to_string(&mut output).is_err() {
        return String::new();
    }
    const MAX_CHARS: usize = 4000;
    let char_count = output.chars().count();
    if char_count > MAX_CHARS {
        output.chars().skip(char_count - MAX_CHARS).collect()
    } else {
        output
    }
}

fn daemon_log_has_fatal_startup_error(output: &str) -> bool {
    output.contains("Traceback (most recent call last)")
        || output.contains("Failed to execute script")
        || output.contains("[PYI-")
}

async fn wait_for_provider_api(
    timeout: Duration,
    daemon_log_path: Option<&Path>,
    daemon_log_offset: u64,
) -> Result<(), String> {
    let started_at = Instant::now();
    let mut last_log_at = Instant::now();

    loop {
        if provider_is_listening() {
            eprintln!(
                "[provider-sidecar] Provider API is listening on {}:{} after {:.2}s",
                PROVIDER_HOST,
                PROVIDER_PORT,
                started_at.elapsed().as_secs_f64()
            );
            return Ok(());
        }

        if let Some(path) = daemon_log_path {
            let daemon_log = read_daemon_log_since(path, daemon_log_offset);
            if daemon_log_has_fatal_startup_error(&daemon_log) {
                return Err(format!(
                    "Provider daemon exited before opening API port {}:{}:\n{}",
                    PROVIDER_HOST,
                    PROVIDER_PORT,
                    daemon_log.trim()
                ));
            }
        }

        if started_at.elapsed() >= timeout {
            let daemon_log = daemon_log_path
                .map(|path| read_daemon_log_since(path, daemon_log_offset))
                .unwrap_or_default();
            if !daemon_log.trim().is_empty() {
                return Err(format!(
                    "Provider daemon did not open API port {}:{} within {:.0}s. Daemon output:\n{}",
                    PROVIDER_HOST,
                    PROVIDER_PORT,
                    timeout.as_secs_f64(),
                    daemon_log.trim()
                ));
            }
            return Err(format!(
                "Provider daemon did not open API port {}:{} within {:.0}s",
                PROVIDER_HOST,
                PROVIDER_PORT,
                timeout.as_secs_f64()
            ));
        }

        if last_log_at.elapsed() >= Duration::from_secs(5) {
            eprintln!(
                "[provider-sidecar] Waiting for provider API on {}:{} elapsed={:.2}s",
                PROVIDER_HOST,
                PROVIDER_PORT,
                started_at.elapsed().as_secs_f64()
            );
            last_log_at = Instant::now();
        }

        std::thread::sleep(Duration::from_millis(500));
    }
}

async fn run_provider_sidecar(app: tauri::AppHandle, args: &[&str]) -> Result<(), String> {
    let output = run_provider_sidecar_output(app, args).await?;

    if output.status.success() {
        return Ok(());
    }

    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    Err(if stderr.is_empty() { stdout } else { stderr })
}

async fn run_provider_sidecar_output(
    app: tauri::AppHandle,
    args: &[&str],
) -> Result<tauri_plugin_shell::process::Output, String> {
    provider_sidecar_command(&app)?
        .args(args)
        .output()
        .await
        .map_err(|err| err.to_string())
}

async fn run_secure_setup_stream(app: tauri::AppHandle) -> Result<Value, String> {
    let (mut rx, _child) = provider_sidecar_command(&app)?
        .args(["secure-setup", "check", "--json-stream"])
        .spawn()
        .map_err(|err| err.to_string())?;

    let mut last_status: Option<Value> = None;
    let mut stdout = String::new();
    let mut stderr = String::new();
    while let Some(event) = rx.recv().await {
        match event {
            CommandEvent::Stdout(line) => {
                let text = String::from_utf8_lossy(&line).trim().to_string();
                if text.is_empty() {
                    continue;
                }
                if let Some(mut status) = parse_setup_status(&text) {
                    ensure_host_requirements_success(&mut status);
                    emit_setup_status(&app, status.clone());
                    last_status = Some(status);
                } else {
                    if !stdout.is_empty() {
                        stdout.push('\n');
                    }
                    stdout.push_str(&text);
                }
            }
            CommandEvent::Stderr(line) => {
                let text = String::from_utf8_lossy(&line).trim().to_string();
                if !text.is_empty() {
                    eprintln!("[provider-sidecar] {}", text);
                    if !stderr.is_empty() {
                        stderr.push('\n');
                    }
                    stderr.push_str(&text);
                }
            }
            CommandEvent::Error(err) => return Err(err),
            CommandEvent::Terminated(payload) => {
                if payload.code == Some(0) {
                    return last_status
                        .ok_or_else(|| "Secure setup produced no status updates".to_string());
                }
                let output = merge_output(&stdout, &stderr);
                if last_status.is_none() && json_stream_unsupported(&output) {
                    return run_secure_setup_once(app.clone()).await;
                }
                return Err(last_status
                    .as_ref()
                    .and_then(|status| serde_json::to_string(status).ok())
                    .unwrap_or_else(|| {
                        if output.is_empty() {
                            "Secure setup failed".to_string()
                        } else {
                            output
                        }
                    }));
            }
            _ => {}
        }
    }

    Err("Secure setup ended before reporting completion".to_string())
}

async fn provider_requirements_stream(
    app: tauri::AppHandle,
    status: &mut Value,
) -> Result<ProviderRequirements, String> {
    let (mut rx, _child) = provider_sidecar_command(&app)?
        .args(["requirements", "check", "--json-stream"])
        .spawn()
        .map_err(|err| err.to_string())?;

    let mut result: Option<ProviderRequirements> = None;
    let mut stdout = String::new();
    let mut stderr = String::new();
    while let Some(event) = rx.recv().await {
        match event {
            CommandEvent::Stdout(line) => {
                let text = String::from_utf8_lossy(&line).trim().to_string();
                if text.is_empty() {
                    continue;
                }
                match serde_json::from_str::<Value>(&text) {
                    Ok(value) if value.get("type").and_then(Value::as_str) == Some("progress") => {
                        if let Some(detail) = value.get("detail").and_then(Value::as_str) {
                            eprintln!("[provider-sidecar] - {}", detail);
                            set_stage(status, "host_requirements", "running", detail);
                            emit_setup_status(&app, status.clone());
                        }
                    }
                    Ok(value) if value.get("type").and_then(Value::as_str) == Some("result") => {
                        if let Some(raw_result) = value.get("result") {
                            result = Some(
                                serde_json::from_value(raw_result.clone())
                                    .map_err(|err| err.to_string())?,
                            );
                        }
                    }
                    _ => {
                        if !stdout.is_empty() {
                            stdout.push('\n');
                        }
                        stdout.push_str(&text);
                    }
                }
            }
            CommandEvent::Stderr(line) => {
                let text = String::from_utf8_lossy(&line).trim().to_string();
                if !text.is_empty() {
                    eprintln!("[provider-sidecar] {}", text);
                    if !stderr.is_empty() {
                        stderr.push('\n');
                    }
                    stderr.push_str(&text);
                }
            }
            CommandEvent::Error(err) => return Err(err),
            CommandEvent::Terminated(payload) => {
                if let Some(requirements) = result {
                    if requirements.compatible {
                        set_stage(status, "host_requirements", "success", "ready");
                    } else {
                        set_stage(
                            status,
                            "host_requirements",
                            "failed",
                            requirements.error.as_deref().unwrap_or("blocked"),
                        );
                    }
                    emit_setup_status(&app, status.clone());
                    return Ok(requirements);
                }
                let output = merge_output(&stdout, &stderr);
                if payload.code == Some(0) {
                    return Err("Provider requirements check produced no output".to_string());
                }
                return Err(if output.is_empty() {
                    "Provider requirements check failed".to_string()
                } else {
                    output
                });
            }
            _ => {}
        }
    }

    Err("Provider requirements check ended before reporting completion".to_string())
}

#[tauri::command]
async fn start_provider(app: tauri::AppHandle) -> Result<(), String> {
    let (admin_authenticated, _) = provider_admin_auth_status();
    if provider_is_listening() && !admin_authenticated {
        eprintln!("[provider-sidecar] Running provider rejected desktop admin token; stopping stale daemon");
        let _ = run_provider_sidecar(app.clone(), &["stop"]).await;
    }

    let mut status = setup_status_starting();
    emit_setup_status(&app, status.clone());
    eprintln!("[provider-sidecar] Checking provider host requirements");
    let requirements_started_at = Instant::now();
    let requirements = provider_requirements_stream(app.clone(), &mut status).await?;
    eprintln!(
        "[provider-sidecar] Provider host requirements finished in {:.2}s",
        requirements_started_at.elapsed().as_secs_f64()
    );
    if !requirements.compatible {
        return Err(requirements
            .error
            .unwrap_or_else(|| "Multipass is not installed or is not responding".to_string()));
    }
    eprintln!("[provider-sidecar] Starting secure endpoint setup");
    set_stage(&mut status, "public_ip", "running", "checking");
    emit_setup_status(&app, status);
    let mut status = run_secure_setup_stream(app.clone()).await?;
    ensure_host_requirements_success(&mut status);
    eprintln!("[provider-sidecar] Secure endpoint setup finished");
    mark_provider_daemon_starting(&mut status);
    emit_setup_status(&app, status.clone());
    eprintln!("[provider-sidecar] Starting provider daemon");
    let daemon_started_at = Instant::now();
    let daemon_log_path = daemon_stdio_log_path();
    let daemon_log_offset = daemon_log_path.as_deref().map(file_len).unwrap_or_default();
    // Desktop already ran secure setup with live progress; avoid a duplicate
    // daemon preflight that would be invisible to the startup UI.
    if let Err(err) =
        run_provider_sidecar(app.clone(), &["start", "--daemon", "--no-verify-port"]).await
    {
        let detail = format!("Provider daemon command failed: {err}");
        mark_provider_daemon_failed(&mut status, &detail);
        emit_setup_status(&app, status);
        return Err(detail);
    }
    eprintln!(
        "[provider-sidecar] Provider daemon command finished in {:.2}s; waiting for API",
        daemon_started_at.elapsed().as_secs_f64()
    );
    if let Err(err) = wait_for_provider_api(
        PROVIDER_START_TIMEOUT,
        daemon_log_path.as_deref(),
        daemon_log_offset,
    )
    .await
    {
        mark_provider_daemon_failed(&mut status, &err);
        emit_setup_status(&app, status);
        return Err(err);
    }
    mark_provider_daemon_started(&mut status);
    emit_setup_status(&app, status);
    Ok(())
}

fn ensure_host_requirements_success(status: &mut Value) {
    let Some(stages) = status.get_mut("stages").and_then(Value::as_array_mut) else {
        return;
    };
    if let Some(stage) = stages
        .iter_mut()
        .find(|stage| stage.get("name").and_then(Value::as_str) == Some("host_requirements"))
    {
        stage["state"] = json!("success");
        stage["detail"] = json!("ready");
        return;
    }
    stages.insert(
        0,
        json!({"name": "host_requirements", "state": "success", "label": "Checking host requirements", "detail": "ready"}),
    );
}

#[tauri::command]
async fn stop_provider(app: tauri::AppHandle) -> Result<(), String> {
    run_provider_sidecar(app, &["stop"]).await
}

#[tauri::command]
fn provider_status() -> ProviderStatus {
    let running = provider_is_listening();
    let (admin_authenticated, admin_auth_error) = provider_admin_auth_status();
    ProviderStatus {
        running,
        api_base_url: provider_api_base_url_value(),
        admin_authenticated,
        admin_auth_error,
    }
}

#[tauri::command]
fn provider_api_base_url() -> String {
    provider_api_base_url_value()
}

#[tauri::command]
fn provider_admin_token() -> Result<String, String> {
    read_or_create_admin_token()
}

#[tauri::command]
async fn provider_requirements(app: tauri::AppHandle) -> Result<ProviderRequirements, String> {
    let output = run_provider_sidecar_output(app, &["requirements", "check", "--json"]).await?;
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if !stdout.is_empty() {
        return serde_json::from_str(&stdout).map_err(|err| err.to_string());
    }

    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    Err(if stderr.is_empty() {
        "Provider requirements check produced no output".to_string()
    } else {
        stderr
    })
}

pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            start_provider,
            stop_provider,
            provider_status,
            provider_api_base_url,
            provider_admin_token,
            provider_requirements
        ])
        .build(tauri::generate_context!())
        .expect("failed to build Golem Provider desktop app");

    let stopping_provider = Arc::new(AtomicBool::new(false));
    app.run(move |app_handle, event| {
        if let tauri::RunEvent::ExitRequested { api, .. } = event {
            if stopping_provider.swap(true, Ordering::SeqCst) {
                return;
            }

            api.prevent_exit();
            let app_handle = app_handle.clone();
            tauri::async_runtime::spawn(async move {
                if let Err(err) = run_provider_sidecar(app_handle.clone(), &["stop"]).await {
                    eprintln!("[provider-sidecar] Failed to stop provider on app exit: {err}");
                }
                app_handle.exit(0);
            });
        }
    });
}
