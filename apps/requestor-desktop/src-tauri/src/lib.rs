use serde::Serialize;
use std::env;

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

fn runtime_config() -> RequestorRuntimeConfig {
    RequestorRuntimeConfig {
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

#[tauri::command]
fn requestor_runtime_config() -> Result<RequestorRuntimeConfig, String> {
    Ok(runtime_config())
}

pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![requestor_runtime_config])
        .run(tauri::generate_context!())
        .expect("failed to run Golem Requestor desktop app");
}
