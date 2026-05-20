# Provider Desktop Data Catalogue

This document lists the information the provider can currently show in the
desktop app. The examples are realistic sample values, not fixed values.

## Service State

```yaml
provider_service: running
api_base_url: http://127.0.0.1:7466/api/v1
```

Other possible service states:

```yaml
provider_service: stopped
provider_service: checking
provider_service: start_failed
provider_service: stop_failed
```

Example failure:

```yaml
provider_service: start_failed
message: Provider port 7466 is already in use
```

## Provider Identity

```yaml
provider_id: "0x8A41c1F27b2dA7e52E7F6D6F44C6b6d55B815122"
stream_payment_address: "0x2d5F7c6D4a9B12a4e0A19E48E23b5Df6A54f1031"
glm_token_address: "0x55555555555556AcFf9C332Ed151758858bd7a26"
eth_token_address: "0x55555555555556AcFf9C332Ed151758858bd7a26"
ip_address: "91.12.44.108"
country: "resolved ISO country code"
platform: "darwin-arm64"
```

Fields can also be empty when not configured yet:

```yaml
ip_address: null
country: null
platform: null
```

## Provider Overview

```yaml
status: running
environment: production
network: mainnet
```

Resource examples:

```yaml
total_resources:
  cpu: 8
  memory: 32
  storage: 500

available_resources:
  cpu: 6
  memory: 24
  storage: 430
```

Pricing examples:

```yaml
usd_per_core_month: 12.00
usd_per_gb_ram_month: 4.00
usd_per_gb_storage_month: 0.20
glm_per_core_month: 53.21891
glm_per_gb_ram_month: 17.73963
glm_per_gb_storage_month: 0.88698
```

VM summary example:

```yaml
vms:
  - id: requestor-demo
    status: running
    ssh_port: 50804
    resources:
      cpu: 2
      memory: 4
      storage: 20
```

## Virtual Machines

One VM exposes:

```yaml
id: requestor-demo
name: requestor-demo
status: running
resources:
  cpu: 2
  memory: 4
  storage: 20
ip_address: "10.171.42.18"
ssh_port: 50804
lifecycle_stage: running
status_message: VM is online
progress: 100
transitioning: false
next_poll_seconds: 8
created_at: "2026-05-13T09:15:24.718Z"
updated_at: "2026-05-13T09:17:02.108Z"
error_message: null
```

Possible VM statuses:

```yaml
status: creating
status: starting
status: restarting
status: running
status: delayed_shutdown
status: suspending
status: suspended
status: stopping
status: stopped
status: error
status: deleted
status: unknown
```

Transitional VM example:

```yaml
id: requestor-demo
status: creating
lifecycle_stage: configuring_access
status_message: Waiting for SSH access
progress: 90
transitioning: true
next_poll_seconds: 2
ssh_port: null
```

Error example:

```yaml
id: requestor-demo
status: error
status_message: VM requires attention
progress: 100
transitioning: false
error_message: Multipass failed to start the VM
```

## Available VM Images

```yaml
images:
  - alias: "24.04"
    version: "Ubuntu 24.04 LTS"
    description: "Ubuntu Noble"
  - alias: "22.04"
    version: "Ubuntu 22.04 LTS"
    description: "Ubuntu Jammy"
```

## New VM Details

The provider accepts this information when creating a VM:

```yaml
name: requestor-demo
size: medium
image: "24.04"
ssh_key: "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA..."
stream_id: 42
```

Instead of a preset size, exact resources can be used:

```yaml
resources:
  cpu: 2
  memory: 4
  storage: 20
```

Preset sizes:

```yaml
small:
  cpu: 1
  memory: 1
  storage: 10

medium:
  cpu: 2
  memory: 4
  storage: 20

large:
  cpu: 4
  memory: 8
  storage: 40

xlarge:
  cpu: 8
  memory: 16
  storage: 80
```

VM name rules:

```yaml
allowed: requestor-demo-1
not_allowed: Requestor Demo
not_allowed: requestor--demo
not_allowed: -requestor-demo
not_allowed: requestor-demo-
```

SSH key rules:

```yaml
allowed_prefix: "ssh-rsa "
allowed_prefix: "ssh-ed25519 "
```

## VM Creation Progress

When creation runs in the background, the provider exposes:

```yaml
job_id: "create-requestor-demo-20260513-091524"
vm_id: requestor-demo
status: creating
lifecycle_stage: queued
status_message: Queued VM creation
progress: 0
transitioning: true
next_poll_seconds: 2
created_at: "2026-05-13T09:15:24.718Z"
updated_at: "2026-05-13T09:15:24.718Z"
error: null
```

Later example:

```yaml
job_id: "create-requestor-demo-20260513-091524"
vm_id: requestor-demo
status: creating
lifecycle_stage: configuring_access
status_message: Waiting for SSH access
progress: 90
transitioning: true
next_poll_seconds: 2
error: null
```

Failed creation example:

```yaml
job_id: "create-requestor-demo-20260513-091524"
vm_id: requestor-demo
status: error
lifecycle_stage: failed
status_message: VM creation failed
progress: 100
transitioning: false
error: Not enough available memory
```

## VM Access

Ready access example:

```yaml
ssh_host: "91.12.44.108"
ssh_port: 50804
ssh_user: ubuntu
vm_id: requestor-demo
multipass_name: requestor-demo-20260513-091524
```

Pending access example:

```yaml
vm_id: requestor-demo
multipass_name: requestor-demo-20260513-091524
ssh_user: ubuntu
status: creating
lifecycle_stage: configuring_access
status_message: Waiting for SSH access
progress: 90
transitioning: true
next_poll_seconds: 2
ssh_port: null
```

## Payment Streams

Stream example:

```yaml
vm_id: requestor-demo
stream_id: 42
verified: true
reason: ok
```

On-chain values:

```yaml
token: "0x55555555555556AcFf9C332Ed151758858bd7a26"
sender: "0x6fA18C92a21fE64c1C46c8A67F400103842D4421"
recipient: "0x8A41c1F27b2dA7e52E7F6D6F44C6b6d55B815122"
startTime: 1778660124
stopTime: 1778746524
ratePerSecond: 100000000000000
deposit: 8640000000000000000
withdrawn: 1800000000000000000
halted: false
```

Computed values:

```yaml
now: 1778674524
remaining_seconds: 72000
vested_wei: 1440000000000000000
withdrawable_wei: 0
```

Problem examples:

```yaml
verified: false
reason: stream recipient does not match provider
```

```yaml
verified: false
reason: no stream mapped for this VM
```

```yaml
halted: true
reason: stream is halted
```

## Monitoring Overview

Provider monitoring example:

```yaml
status: healthy
last_sample_at: "2026-05-13T10:15:30Z"
```

Host metric examples:

```yaml
cpu_percent: 34.7
memory_used_bytes: 12884901888
memory_total_bytes: 34359738368
disk_used_bytes: 75161927680
disk_total_bytes: 536870912000
load_1m: 1.42
network_rx_bytes: 842004221
network_tx_bytes: 328901100
```

VM metric examples:

```yaml
vm_id: requestor-demo
cpu_percent: 18.4
memory_used_bytes: 1717986918
memory_total_bytes: 4294967296
disk_used_bytes: 8589934592
disk_total_bytes: 21474836480
network_rx_bytes: 42890210
network_tx_bytes: 10039282
agent_version: "0.1.0"
```

Metric sample example:

```yaml
scope: vm
source: guest_agent
metric: cpu_percent
value: 18.4
unit: percent
timestamp: "2026-05-13T10:15:30Z"
vm_id: requestor-demo
```

Metric sources:

```yaml
source: infrastructure
source: guest_agent
```

Metric scopes:

```yaml
scope: host
scope: vm
```

History ranges:

```yaml
range: 1h
range: 6h
range: 24h
range: 7d
range: 30d
```

## Alerts

Active alert example:

```yaml
name: High CPU
severity: warning
metric: cpu_percent
scope: vm
vm_id: requestor-demo
value: 94.2
threshold: 90
message: CPU has been above 90% for 5 minutes
```

Alert rule example:

```yaml
id: 3
name: High CPU
metric: cpu_percent
scope: vm
source: guest_agent
operator: ">"
threshold: 90
duration_seconds: 300
severity: warning
enabled: true
```

## Webhooks

Webhook example:

```yaml
id: 2
name: Ops alerts
url: "https://example.com/golem-alerts"
enabled: true
service_type: discord # generic_json | discord | slack
events:
  - alert.fired
  - alert.resolved
  - vm.failed
  - payment.stream.lost
template:
  title: "{{summary}}"
  message: "{{summary}}"
  color: severity
  fields:
    - name: Event
      value: "{{event.type}}"
    - name: Resource
      value: "{{resource.id}}"
  footer: Golem Provider
last_status: success
last_http_status: 204
last_error: null
last_delivered_at: "2026-05-13T10:10:02Z"
```

Webhook preview:

```yaml
service_type: discord
payload:
  content: "VM requestor-vm-id is ready"
  embeds:
    - title: "VM is online"
      description: "VM requestor-vm-id is ready"
      color: 3909878
      fields:
        - name: Event
          value: vm.ready
          inline: true
```

Webhook test success:

```yaml
ok: true
status: 204
error: null
event_id: "3c812df0-63d4-4de4-95a0-11ef09c0c9ef"
payload:
  event_type: vm.ready
```

Webhook test failure:

```yaml
ok: false
status: 500
error: "server returned 500"
event_id: "3c812df0-63d4-4de4-95a0-11ef09c0c9ef"
payload: {}
```

Webhook delivery attempt:

```yaml
id: 9
webhook_id: 2
event_id: "3c812df0-63d4-4de4-95a0-11ef09c0c9ef"
event_type: payment.stream.lost
attempt: 2
status: success
http_status: 204
error: null
attempted_at: "2026-05-13T10:10:02Z"
```

## Health Data Available Through the Provider CLI

This information exists in the provider, but is not yet exposed directly to the
desktop app screens.

```yaml
overall_status: healthy
issues: []
installed_version: "0.1.0"
latest_version: "0.1.0"
update_available: false
environment: production
network: mainnet
dev_mode: false
```

Multipass health:

```yaml
multipass_ok: true
multipass_path: "/usr/local/bin/multipass"
multipass_version: "multipass 1.14.1"
```

Provider port health:

```yaml
provider_port: 7466
provider_host: "0.0.0.0"
provider_local_ok: true
provider_external_status: reachable
```

SSH port health:

```yaml
ssh_port_range: [50800, 50900]
ssh_status: ok
usable_free: 83
in_use: 2
unreachable: 0
not_listening: 0
```

Example health issue:

```yaml
overall_status: error
issues:
  - Multipass not available
  - No externally reachable SSH ports
```

## Data Gaps

These areas exist partly in the provider, but are not yet available as simple
desktop app data.

```yaml
pricing_edit: not_available_yet
stream_monitor_settings: not_available_yet
auto_withdraw_settings: not_available_yet
wallet_faucet_request: not_available_yet
stream_withdraw_action: not_available_yet
alert_rule_update: not_available_yet
alert_rule_delete: not_available_yet
```
