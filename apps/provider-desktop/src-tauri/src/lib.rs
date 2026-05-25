use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, Mutex,
};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tauri::Emitter;
use tauri_plugin_shell::process::{Command, CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const PROVIDER_HOST: &str = "127.0.0.1";
const PROVIDER_PORT: u16 = 7466;
const PROVIDER_START_TIMEOUT: Duration = Duration::from_secs(180);
const PAYMENTS_NETWORK: &str = "hoodi";
const PAYMENTS_RPC_URL: &str = "https://rpc.hoodi.ethpandaops.io";
const PAYMENTS_WS_URL: &str = "wss://ethereum-hoodi-rpc.publicnode.com";
const STREAM_PAYMENT_ADDRESS: &str = "0xb5a225b2f82D3eFe743D95bA7Fe3BbC475C0a12E";
const GLM_TOKEN_ADDRESS: &str = "0x55555555555556AcFf9C332Ed151758858bd7a26";
static PROVIDER_FOREGROUND_CHILD: Mutex<Option<CommandChild>> = Mutex::new(None);
static DESKTOP_LOG_LOCK: Mutex<()> = Mutex::new(());

#[derive(Default)]
struct ProviderProcessState {
    output: String,
    failure: Option<String>,
}

type ProviderProcessStateHandle = Arc<Mutex<ProviderProcessState>>;

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

fn provider_desktop_log(message: impl AsRef<str>) {
    let message = redact_sensitive_process_output(message.as_ref());
    eprintln!("{message}");

    let Ok(_guard) = DESKTOP_LOG_LOCK.lock() else {
        return;
    };
    let Ok(log_path) = provider_desktop_log_path() else {
        return;
    };
    if let Some(parent) = log_path.parent() {
        if fs::create_dir_all(parent).is_err() {
            return;
        }
    }
    let Ok(mut file) = OpenOptions::new().create(true).append(true).open(log_path) else {
        return;
    };
    let _ = writeln!(file, "{} {}", unix_timestamp_seconds(), message);
}

fn unix_timestamp_seconds() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0)
}

fn provider_desktop_log_path() -> Result<PathBuf, String> {
    Ok(provider_home_dir()?
        .join("Library/Application Support/Golem Provider/logs/provider-desktop.log"))
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
    provider_desktop_log(format!(
        "[provider-sidecar] Preparing sidecar command vm_data_dir={vm_data_dir}"
    ));
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
                ("GOLEM_PROVIDER_DISABLE_RELOAD", "1".to_string()),
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

fn trim_process_output(output: &str) -> String {
    const MAX_CHARS: usize = 4000;
    let trimmed = output.trim();
    let char_count = trimmed.chars().count();
    if char_count > MAX_CHARS {
        trimmed.chars().skip(char_count - MAX_CHARS).collect()
    } else {
        trimmed.to_string()
    }
}

fn redact_sensitive_process_output(output: &str) -> String {
    output
        .lines()
        .map(redact_sensitive_process_output_line)
        .collect::<Vec<_>>()
        .join("\n")
}

fn redact_sensitive_process_output_line(line: &str) -> String {
    const SECRET_ASSIGNMENTS: [&str; 1] = ["GOLEM_PROVIDER_ADMIN_TOKEN="];
    for assignment in SECRET_ASSIGNMENTS {
        if let Some(index) = line.find(assignment) {
            return format!("{}{}<redacted>", &line[..index], assignment);
        }
    }
    line.to_string()
}

fn provider_port_conflict_detail(output: &str) -> String {
    trim_process_output(
        &redact_sensitive_process_output(output)
            .lines()
            .filter(|line| provider_output_has_port_conflict(line) || line.contains("ERROR:"))
            .collect::<Vec<_>>()
            .join("\n"),
    )
}

fn provider_port_in_use_message() -> String {
    format!(
        "Provider API port {PROVIDER_HOST}:{PROVIDER_PORT} is already in use. Stop the process using that port and start Golem Provider again."
    )
}

fn provider_process_failure(output: &str, exit_code: Option<i32>) -> String {
    let sanitized_output = redact_sensitive_process_output(output);
    if provider_output_has_port_conflict(&sanitized_output) {
        let detail = provider_port_conflict_detail(&sanitized_output);
        if detail.is_empty() {
            return provider_port_in_use_message();
        }
        return format!("{}\n{}", provider_port_in_use_message(), detail);
    }
    if provider_output_has_cli_option_error(&sanitized_output) {
        let detail = provider_cli_option_error_detail(&sanitized_output);
        if detail.is_empty() {
            return "Provider service failed while parsing startup options.".to_string();
        }
        return format!("Provider service failed while parsing startup options.\n{detail}");
    }
    let detail = trim_process_output(&sanitized_output);
    if detail.is_empty() {
        return format!(
            "Provider service exited before the API became ready. Exit code: {exit_code:?}"
        );
    }
    format!(
        "Provider service exited before the API became ready. Exit code: {exit_code:?}\n{detail}"
    )
}

fn provider_output_has_port_conflict(output: &str) -> bool {
    output.contains("Address already in use")
        || output.contains("address already in use")
        || output.contains("Errno 48")
        || output.contains("EADDRINUSE")
}

fn provider_output_has_cli_option_error(output: &str) -> bool {
    output.contains("No such option:")
}

fn provider_cli_option_error_detail(output: &str) -> String {
    trim_process_output(
        &redact_sensitive_process_output(output)
            .lines()
            .filter(|line| {
                provider_output_has_cli_option_error(line)
                    || line.contains("Usage: golem-provider")
                    || line.contains("Try 'golem-provider --help'")
                    || line.contains("Error")
            })
            .collect::<Vec<_>>()
            .join("\n"),
    )
}

fn record_provider_process_output(process_state: &ProviderProcessStateHandle, text: &str) {
    if text.trim().is_empty() {
        return;
    }
    if let Ok(mut state) = process_state.lock() {
        if !state.output.is_empty() {
            state.output.push('\n');
        }
        state.output.push_str(text);
        if (provider_output_has_port_conflict(&state.output)
            || provider_output_has_cli_option_error(&state.output))
            && state.failure.is_none()
        {
            state.failure = Some(provider_process_failure(&state.output, None));
        }
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

fn mark_provider_service_starting(status: &mut Value) {
    status["message"] = json!("Starting provider service.");
    set_stage(status, "provider_start", "running", "starting service");
}

fn mark_provider_service_started(status: &mut Value) {
    status["message"] = json!("Provider service started.");
    set_stage(status, "provider_start", "success", "API listening");
}

fn mark_provider_service_failed(status: &mut Value, detail: &str) {
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

fn provider_process_failed(process_state: &ProviderProcessStateHandle) -> Option<String> {
    process_state
        .lock()
        .ok()
        .and_then(|state| state.failure.clone())
}

async fn wait_for_provider_api(
    timeout: Duration,
    process_state: &ProviderProcessStateHandle,
) -> Result<(), String> {
    let process_state = Arc::clone(process_state);
    tauri::async_runtime::spawn_blocking(move || {
        wait_for_provider_api_blocking(timeout, &process_state)
    })
    .await
    .map_err(|err| format!("Provider API readiness wait failed: {err}"))?
}

fn wait_for_provider_api_blocking(
    timeout: Duration,
    process_state: &ProviderProcessStateHandle,
) -> Result<(), String> {
    let started_at = Instant::now();
    let mut last_log_at = Instant::now();

    loop {
        if let Some(failure) = provider_process_failed(process_state) {
            return Err(failure);
        }

        if provider_is_listening() {
            provider_desktop_log(format!(
                "[provider-sidecar] Provider API is listening on {}:{} after {:.2}s",
                PROVIDER_HOST,
                PROVIDER_PORT,
                started_at.elapsed().as_secs_f64()
            ));
            return Ok(());
        }

        if started_at.elapsed() >= timeout {
            return Err(format!(
                "Provider service did not open API port {}:{} within {:.0}s",
                PROVIDER_HOST,
                PROVIDER_PORT,
                timeout.as_secs_f64()
            ));
        }

        if last_log_at.elapsed() >= Duration::from_secs(5) {
            provider_desktop_log(format!(
                "[provider-sidecar] Waiting for provider API on {}:{} elapsed={:.2}s",
                PROVIDER_HOST,
                PROVIDER_PORT,
                started_at.elapsed().as_secs_f64()
            ));
            last_log_at = Instant::now();
        }

        std::thread::sleep(Duration::from_millis(500));
    }
}

async fn run_provider_sidecar_output(
    app: tauri::AppHandle,
    args: &[&str],
) -> Result<tauri_plugin_shell::process::Output, String> {
    provider_desktop_log(format!(
        "[provider-sidecar] Running sidecar output command args={args:?}"
    ));
    provider_sidecar_command(&app)?
        .args(args)
        .output()
        .await
        .map_err(|err| {
            provider_desktop_log(format!(
                "[provider-sidecar] Sidecar output command failed args={args:?} error={err}"
            ));
            err.to_string()
        })
}

fn spawn_provider_service(app: tauri::AppHandle) -> Result<ProviderProcessStateHandle, String> {
    provider_desktop_log("[provider-sidecar] Stopping any previously spawned provider child");
    stop_spawned_provider_child();
    let process_state = Arc::new(Mutex::new(ProviderProcessState::default()));
    provider_desktop_log("[provider-sidecar] Spawning provider service command");
    let (mut rx, child) = provider_sidecar_command(&app)?
        .args(["start", "--no-verify-port"])
        .spawn()
        .map_err(|err| {
            provider_desktop_log(format!(
                "[provider-sidecar] Provider service spawn failed: {err}"
            ));
            err.to_string()
        })?;
    let child_pid = child.pid();
    provider_desktop_log(format!(
        "[provider-sidecar] Provider service child spawned pid={child_pid}"
    ));
    if let Ok(mut current_child) = PROVIDER_FOREGROUND_CHILD.lock() {
        *current_child = Some(child);
    }
    let process_state_for_events = Arc::clone(&process_state);
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    let text = String::from_utf8_lossy(&line).trim().to_string();
                    if !text.is_empty() {
                        provider_desktop_log(format!("[provider-sidecar] {}", text));
                        record_provider_process_output(&process_state_for_events, &text);
                    }
                }
                CommandEvent::Stderr(line) => {
                    let text = String::from_utf8_lossy(&line).trim().to_string();
                    if !text.is_empty() {
                        provider_desktop_log(format!("[provider-sidecar] {}", text));
                        record_provider_process_output(&process_state_for_events, &text);
                    }
                }
                CommandEvent::Error(err) => {
                    provider_desktop_log(format!(
                        "[provider-sidecar] Provider service stream error: {err}"
                    ));
                    if let Ok(mut state) = process_state_for_events.lock() {
                        state.failure = Some(format!("Provider service stream error: {err}"));
                    }
                }
                CommandEvent::Terminated(payload) => {
                    provider_desktop_log(format!(
                        "[provider-sidecar] Provider service exited with code {:?}",
                        payload.code
                    ));
                    let exited_before_ready = !provider_is_listening();
                    if exited_before_ready || payload.code != Some(0) {
                        if let Ok(mut state) = process_state_for_events.lock() {
                            state.failure =
                                Some(provider_process_failure(&state.output, payload.code));
                        }
                    }
                    if let Ok(mut current_child) = PROVIDER_FOREGROUND_CHILD.lock() {
                        let should_clear = current_child
                            .as_ref()
                            .map(|child| child.pid() == child_pid)
                            .unwrap_or(false);
                        if should_clear {
                            *current_child = None;
                        }
                    }
                    break;
                }
                _ => {}
            }
        }
    });
    Ok(process_state)
}

fn stop_spawned_provider_child() {
    let child = PROVIDER_FOREGROUND_CHILD
        .lock()
        .ok()
        .and_then(|mut current_child| current_child.take());
    if let Some(child) = child {
        provider_desktop_log(format!(
            "[provider-sidecar] Killing spawned provider child pid={}",
            child.pid()
        ));
        let _ = child.kill();
    }
}

async fn run_secure_setup_stream(app: tauri::AppHandle) -> Result<Value, String> {
    provider_desktop_log("[provider-sidecar] Spawning secure setup stream command");
    let (mut rx, _child) = provider_sidecar_command(&app)?
        .args(["secure-setup", "check", "--json-stream"])
        .spawn()
        .map_err(|err| {
            provider_desktop_log(format!(
                "[provider-sidecar] Secure setup stream spawn failed: {err}"
            ));
            err.to_string()
        })?;

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
                    provider_desktop_log(format!("[provider-sidecar] {}", text));
                    if !stderr.is_empty() {
                        stderr.push('\n');
                    }
                    stderr.push_str(&text);
                }
            }
            CommandEvent::Error(err) => {
                provider_desktop_log(format!(
                    "[provider-sidecar] Secure setup stream error: {err}"
                ));
                return Err(err);
            }
            CommandEvent::Terminated(payload) => {
                provider_desktop_log(format!(
                    "[provider-sidecar] Secure setup stream exited with code {:?}",
                    payload.code
                ));
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
    provider_desktop_log("[provider-sidecar] Spawning requirements stream command");
    let (mut rx, _child) = provider_sidecar_command(&app)?
        .args(["requirements", "check", "--json-stream"])
        .spawn()
        .map_err(|err| {
            provider_desktop_log(format!(
                "[provider-sidecar] Requirements stream spawn failed: {err}"
            ));
            err.to_string()
        })?;

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
                            provider_desktop_log(format!("[provider-sidecar] - {}", detail));
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
                    provider_desktop_log(format!("[provider-sidecar] {}", text));
                    if !stderr.is_empty() {
                        stderr.push('\n');
                    }
                    stderr.push_str(&text);
                }
            }
            CommandEvent::Error(err) => {
                provider_desktop_log(format!(
                    "[provider-sidecar] Requirements stream error: {err}"
                ));
                return Err(err);
            }
            CommandEvent::Terminated(payload) => {
                provider_desktop_log(format!(
                    "[provider-sidecar] Requirements stream exited with code {:?}",
                    payload.code
                ));
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
    provider_desktop_log("[provider-sidecar] Start provider requested");
    let (admin_authenticated, _) = provider_admin_auth_status();
    if provider_is_listening() {
        if admin_authenticated {
            provider_desktop_log(
                "[provider-sidecar] Provider API is already listening with the desktop admin token",
            );
            return Ok(());
        }
        return Err(
            "Provider API is already listening but rejected the desktop admin token. Stop that provider process and start the desktop app again."
                .to_string(),
        );
    }

    let mut status = setup_status_starting();
    emit_setup_status(&app, status.clone());
    provider_desktop_log("[provider-sidecar] Checking provider host requirements");
    let requirements_started_at = Instant::now();
    let requirements = provider_requirements_stream(app.clone(), &mut status).await?;
    provider_desktop_log(format!(
        "[provider-sidecar] Provider host requirements finished in {:.2}s",
        requirements_started_at.elapsed().as_secs_f64()
    ));
    if !requirements.compatible {
        return Err(requirements
            .error
            .unwrap_or_else(|| "Multipass is not installed or is not responding".to_string()));
    }
    provider_desktop_log("[provider-sidecar] Starting secure endpoint setup");
    set_stage(&mut status, "public_ip", "running", "checking");
    emit_setup_status(&app, status);
    let mut status = run_secure_setup_stream(app.clone()).await?;
    ensure_host_requirements_success(&mut status);
    provider_desktop_log("[provider-sidecar] Secure endpoint setup finished");
    mark_provider_service_starting(&mut status);
    emit_setup_status(&app, status.clone());
    if provider_is_listening() {
        let (admin_authenticated, _) = provider_admin_auth_status();
        if admin_authenticated {
            mark_provider_service_started(&mut status);
            emit_setup_status(&app, status);
            return Ok(());
        }
        let detail = format!(
            "{} The process on that port rejected the desktop admin token.",
            provider_port_in_use_message()
        );
        mark_provider_service_failed(&mut status, &detail);
        emit_setup_status(&app, status);
        return Err(detail);
    }
    provider_desktop_log("[provider-sidecar] Starting provider service");
    let service_started_at = Instant::now();
    // Desktop already ran secure setup with live progress. Keep the provider
    // process attached here and let the desktop readiness probe drive the UI.
    let process_state = match spawn_provider_service(app.clone()) {
        Ok(process_state) => process_state,
        Err(err) => {
            let detail = format!("Provider service command failed: {err}");
            mark_provider_service_failed(&mut status, &detail);
            emit_setup_status(&app, status);
            return Err(detail);
        }
    };
    provider_desktop_log(format!(
        "[provider-sidecar] Provider service command spawned in {:.2}s; waiting for API",
        service_started_at.elapsed().as_secs_f64()
    ));
    if let Err(err) = wait_for_provider_api(PROVIDER_START_TIMEOUT, &process_state).await {
        provider_desktop_log(format!(
            "[provider-sidecar] Provider API readiness failed: {err}"
        ));
        mark_provider_service_failed(&mut status, &err);
        emit_setup_status(&app, status);
        return Err(err);
    }
    provider_desktop_log("[provider-sidecar] Provider service started");
    mark_provider_service_started(&mut status);
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
async fn stop_provider(_app: tauri::AppHandle) -> Result<(), String> {
    stop_spawned_provider_child();
    Ok(())
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn provider_process_output_marks_port_conflict_as_failure() {
        let process_state = Arc::new(Mutex::new(ProviderProcessState::default()));

        record_provider_process_output(
            &process_state,
            "ERROR:    [Errno 48] Address already in use",
        );

        let failure = provider_process_failed(&process_state).expect("failure");
        assert!(failure.contains("Provider API port 127.0.0.1:7466 is already in use"));
        assert!(failure.contains("Address already in use"));
    }

    #[test]
    fn provider_process_failure_redacts_admin_token() {
        let output = "\
GOLEM_PROVIDER_ADMIN_TOKEN=secret-token
INFO: startup
ERROR:    [Errno 48] Address already in use";

        let failure = provider_process_failure(output, None);

        assert!(failure.contains("Address already in use"));
        assert!(!failure.contains("secret-token"));
        assert!(!failure.contains("GOLEM_PROVIDER_ADMIN_TOKEN=secret-token"));
    }

    #[test]
    fn provider_process_output_marks_cli_option_error_as_failure() {
        let process_state = Arc::new(Mutex::new(ProviderProcessState::default()));

        record_provider_process_output(
            &process_state,
            "Usage: golem-provider [OPTIONS] COMMAND [ARGS]...",
        );
        record_provider_process_output(
            &process_state,
            "│ No such option: --multiprocessing-fork                                       │",
        );

        let failure = provider_process_failed(&process_state).expect("failure");
        assert!(failure.contains("Provider service failed while parsing startup options"));
        assert!(failure.contains("No such option: --multiprocessing-fork"));
    }

    #[test]
    fn provider_process_failure_reports_non_port_exit_output() {
        let failure = provider_process_failure("ERROR: application startup failed", Some(1));

        assert!(failure.contains("Provider service exited before the API became ready"));
        assert!(failure.contains("ERROR: application startup failed"));
    }

    #[test]
    fn provider_process_failure_reports_zero_exit_before_readiness() {
        let failure =
            provider_process_failure("ERROR: Application startup failed. Exiting.", Some(0));

        assert!(failure.contains("Provider service exited before the API became ready"));
        assert!(failure.contains("ERROR: Application startup failed. Exiting."));
    }
}

pub fn run() {
    provider_desktop_log("[provider-desktop] Launching Golem Provider desktop app");
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
            provider_desktop_log("[provider-desktop] Exit requested");
            if stopping_provider.swap(true, Ordering::SeqCst) {
                return;
            }

            api.prevent_exit();
            let app_handle = app_handle.clone();
            tauri::async_runtime::spawn(async move {
                provider_desktop_log("[provider-desktop] Stopping provider child before exit");
                stop_spawned_provider_child();
                provider_desktop_log("[provider-desktop] Exiting Golem Provider desktop app");
                app_handle.exit(0);
            });
        }
    });
}
