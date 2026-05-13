use rand::{distributions::Alphanumeric, Rng};
use serde::Serialize;
use std::env;
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const PORT_CHECKER_HOST: &str = "127.0.0.1";
const PREFERRED_PORT_CHECKER_PORT: u16 = 9000;
const PROVIDER_API_PORT: u16 = 7466;
const CENTRAL_DISCOVERY_API_URL: &str = "http://195.201.39.101:9001/api/v1";
const STREAM_PAYMENT_ADDRESS: &str = "0x3EaBfECFa1A2Acb99Af4520eB3fc963D2ED0ffE6";
const GLM_TOKEN_ADDRESS: &str = "0x55555555555556AcFf9C332Ed151758858bd7a26";
const EVM_CHAIN_ID: &str = "0x88bb0";
const EVM_CHAIN_NAME: &str = "Ethereum Hoodi";
const EVM_RPC_URL: &str = "https://ethereum-hoodi-rpc.publicnode.com";
const EVM_EXPLORER_URL: &str = "https://hoodi.etherscan.io";

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct RequestorRuntimeConfig {
    port_checker_url: String,
    port_checker_token: String,
    provider_api_port: String,
    discovery_api_url: String,
    discovery_mode: String,
    stream_payment_address: String,
    glm_token_address: String,
    evm_chain_id: String,
    evm_chain_name: String,
    evm_rpc_url: String,
    evm_explorer_url: String,
    golem_environment: String,
    arkiv_dev_rpc_url: String,
    arkiv_dev_ws_url: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct RequestorServicesStatus {
    port_checker_running: bool,
    port_checker_url: String,
}

struct RequestorState {
    inner: Mutex<ManagedPortChecker>,
}

struct ManagedPortChecker {
    child: Option<CommandChild>,
    config: RequestorRuntimeConfig,
}

impl Drop for RequestorState {
    fn drop(&mut self) {
        if let Ok(mut inner) = self.inner.lock() {
            if let Some(child) = inner.child.take() {
                let _ = child.kill();
            }
        }
    }
}

impl RequestorState {
    fn new() -> Self {
        let token = generate_proxy_token();
        let config = runtime_config(PREFERRED_PORT_CHECKER_PORT, token);
        Self {
            inner: Mutex::new(ManagedPortChecker {
                child: None,
                config,
            }),
        }
    }
}

fn runtime_config(port: u16, token: String) -> RequestorRuntimeConfig {
    RequestorRuntimeConfig {
        port_checker_url: format!("http://{PORT_CHECKER_HOST}:{port}"),
        port_checker_token: token,
        provider_api_port: env_or("NEXT_PUBLIC_PROVIDER_API_PORT", &PROVIDER_API_PORT.to_string()),
        discovery_api_url: env_or("NEXT_PUBLIC_DISCOVERY_API_URL", CENTRAL_DISCOVERY_API_URL),
        discovery_mode: env_or("NEXT_PUBLIC_DISCOVERY_MODE", "central"),
        stream_payment_address: env_or(
            "NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS",
            STREAM_PAYMENT_ADDRESS,
        ),
        glm_token_address: env_or("NEXT_PUBLIC_GLM_TOKEN_ADDRESS", GLM_TOKEN_ADDRESS),
        evm_chain_id: env_or("NEXT_PUBLIC_EVM_CHAIN_ID", EVM_CHAIN_ID),
        evm_chain_name: env_or("NEXT_PUBLIC_EVM_CHAIN_NAME", EVM_CHAIN_NAME),
        evm_rpc_url: env_or("NEXT_PUBLIC_EVM_RPC_URL", EVM_RPC_URL),
        evm_explorer_url: env_or("NEXT_PUBLIC_EVM_EXPLORER_URL", EVM_EXPLORER_URL),
        golem_environment: env_or("NEXT_PUBLIC_GOLEM_ENVIRONMENT", "production"),
        arkiv_dev_rpc_url: env_or("NEXT_PUBLIC_ARKIV_DEV_RPC_URL", ""),
        arkiv_dev_ws_url: env_or("NEXT_PUBLIC_ARKIV_DEV_WS_URL", ""),
    }
}

fn env_or(name: &str, fallback: &str) -> String {
    env::var(name)
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| fallback.to_string())
}

fn configured_proxy_token() -> String {
    env::var("NEXT_PUBLIC_PORT_CHECKER_TOKEN")
        .or_else(|_| env::var("PORT_CHECKER_PROXY_TOKEN"))
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(generate_proxy_token)
}

fn generate_proxy_token() -> String {
    rand::thread_rng()
        .sample_iter(&Alphanumeric)
        .take(32)
        .map(char::from)
        .collect()
}

fn is_listening(port: u16) -> bool {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    TcpStream::connect_timeout(&addr, Duration::from_millis(300)).is_ok()
}

fn available_port() -> Result<u16, String> {
    for port in PREFERRED_PORT_CHECKER_PORT..=PREFERRED_PORT_CHECKER_PORT + 20 {
        if TcpListener::bind((PORT_CHECKER_HOST, port)).is_ok() {
            return Ok(port);
        }
    }
    Err("No available local port found for port-checker".to_string())
}

fn start_port_checker(app: tauri::AppHandle) -> Result<RequestorRuntimeConfig, String> {
    let state = app.state::<RequestorState>();
    let mut inner = state.inner.lock().map_err(|err| err.to_string())?;
    if inner.child.is_some() {
        return Ok(inner.config.clone());
    }

    let port = available_port()?;
    let token = configured_proxy_token();
    let config = runtime_config(port, token);
    let (mut rx, child) = app
        .shell()
        .sidecar("golem-port-checker")
        .map_err(|err| err.to_string())?
        .env("PORT_CHECKER_HOST", PORT_CHECKER_HOST)
        .env("PORT_CHECKER_PORT", port.to_string())
        .env("PORT_CHECKER_PROXY_TOKEN", &config.port_checker_token)
        .env("PORT_CHECKER_PROXY_ENABLED", "true")
        .env("GOLEM_ENVIRONMENT", &config.golem_environment)
        .env("PORT_CHECKER_EXPECTED_NETWORK", expected_network(&config))
        .env("CENTRAL_DISCOVERY_API_URL", &config.discovery_api_url)
        .env("ARKIV_RPC_URL", &config.arkiv_dev_rpc_url)
        .env("ARKIV_WS_URL", &config.arkiv_dev_ws_url)
        .spawn()
        .map_err(|err| err.to_string())?;

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    println!("port-checker: {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Stderr(line) => {
                    eprintln!("port-checker: {}", String::from_utf8_lossy(&line));
                }
                _ => {}
            }
        }
    });

    inner.child = Some(child);
    inner.config = config.clone();
    Ok(config)
}

fn expected_network(config: &RequestorRuntimeConfig) -> String {
    env::var("PORT_CHECKER_EXPECTED_NETWORK")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| {
            if config.golem_environment.eq_ignore_ascii_case("development") {
                "development".to_string()
            } else {
                "mainnet".to_string()
            }
        })
}

fn configured_port(config: &RequestorRuntimeConfig) -> Result<u16, String> {
    config
        .port_checker_url
        .rsplit(':')
        .next()
        .ok_or_else(|| "Port-checker URL does not include a port".to_string())?
        .parse::<u16>()
        .map_err(|err| err.to_string())
}

#[tauri::command]
fn requestor_runtime_config(
    app: tauri::AppHandle,
) -> Result<RequestorRuntimeConfig, String> {
    start_port_checker(app)
}

#[tauri::command]
fn requestor_services_status(
    state: tauri::State<RequestorState>,
) -> Result<RequestorServicesStatus, String> {
    let inner = state.inner.lock().map_err(|err| err.to_string())?;
    let port = configured_port(&inner.config)?;
    Ok(RequestorServicesStatus {
        port_checker_running: inner.child.is_some() && is_listening(port),
        port_checker_url: inner.config.port_checker_url.clone(),
    })
}

#[tauri::command]
fn restart_port_checker(app: tauri::AppHandle) -> Result<RequestorRuntimeConfig, String> {
    {
        let state = app.state::<RequestorState>();
        let mut inner = state.inner.lock().map_err(|err| err.to_string())?;
        if let Some(child) = inner.child.take() {
            let _ = child.kill();
        }
    }
    start_port_checker(app)
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(RequestorState::new())
        .setup(|app| {
            start_port_checker(app.handle().clone())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            requestor_runtime_config,
            requestor_services_status,
            restart_port_checker
        ])
        .run(tauri::generate_context!())
        .expect("failed to run Golem Requestor desktop app");
}
