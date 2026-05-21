import os
import subprocess
import time
from typing import Any, Optional

import typer

from .admin_client import (
    DEFAULT_API_BASE_URL,
    ProviderAdminClient,
    ProviderCliError,
    provider_vm_data_dir,
)
from .render import output, print_mapping, print_table

vm_app = typer.Typer(help="Manage rented virtual machines.")
stream_app = typer.Typer(help="Inspect streams and earnings.")
monitor_app = typer.Typer(
    help="Inspect provider monitoring data.",
    invoke_without_command=True,
    no_args_is_help=False,
)
alert_app = typer.Typer(help="Manage alerts.")
webhook_app = typer.Typer(help="Manage webhooks.")
settings_app = typer.Typer(
    help="View and update provider settings.",
    invoke_without_command=True,
    no_args_is_help=False,
)
settings_resources_app = typer.Typer(
    help="View and update offered resources.",
    invoke_without_command=True,
    no_args_is_help=False,
)
settings_pricing_app = typer.Typer(
    help="View, update, and estimate pricing.",
    invoke_without_command=True,
    no_args_is_help=False,
)


def register_headless_commands(cli: typer.Typer) -> None:
    cli.add_typer(vm_app, name="vm")
    cli.add_typer(stream_app, name="stream")
    cli.add_typer(monitor_app, name="monitor")
    cli.add_typer(alert_app, name="alert")
    cli.add_typer(webhook_app, name="webhook")
    cli.add_typer(settings_app, name="settings")


def _client(api: str = DEFAULT_API_BASE_URL, token: Optional[str] = None):
    return ProviderAdminClient(base_url=api, token=token)


def _handle_error(exc: ProviderCliError) -> None:
    typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(code=1)


def _confirm(action: str, yes: bool) -> None:
    if yes:
        return
    if not typer.confirm(action):
        raise typer.Exit(code=1)


@vm_app.command("list")
def vm_list(
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """List rented virtual machines."""
    try:
        rows = _client(api, token).get("/vms")
        if json_out:
            output(rows, json_out=True)
            return
        print_table(
            [
                {
                    "id": vm.get("id"),
                    "status": vm.get("status"),
                    "cpu": (vm.get("resources") or {}).get("cpu"),
                    "memory": (vm.get("resources") or {}).get("memory"),
                    "storage": (vm.get("resources") or {}).get("storage"),
                    "ip": vm.get("ip_address"),
                    "ssh": vm.get("ssh_port"),
                    "updated": vm.get("updated_at"),
                }
                for vm in rows
            ],
            title="Virtual Machines",
        )
    except ProviderCliError as exc:
        _handle_error(exc)


@vm_app.command("show")
def vm_show(
    vm_id: str,
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Show VM details."""
    try:
        output(_client(api, token).get(f"/vms/{vm_id}"), json_out=json_out, title="VM")
    except ProviderCliError as exc:
        _handle_error(exc)


@vm_app.command("access")
def vm_access(
    vm_id: str,
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Show SSH access details for a VM."""
    try:
        data = _client(api, token).get(f"/vms/{vm_id}/access")
        if not json_out and data.get("ssh_host") and data.get("ssh_port"):
            data = {
                **data,
                "ssh_command": (
                    f"ssh {data.get('ssh_user', 'ubuntu')}@{data['ssh_host']} "
                    f"-p {data['ssh_port']}"
                ),
            }
        output(data, json_out=json_out, title="VM Access")
    except ProviderCliError as exc:
        _handle_error(exc)


@vm_app.command("ssh")
def vm_ssh(
    vm_id: str,
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Open an SSH session to a VM."""
    try:
        data = _client(api, token).get(f"/vms/{vm_id}/access")
        host = data.get("ssh_host")
        port = data.get("ssh_port")
        user = data.get("ssh_user") or "ubuntu"
        if not host or not port:
            raise ProviderCliError("VM SSH access is not available yet.")
        raise typer.Exit(
            code=subprocess.call(["ssh", f"{user}@{host}", "-p", str(port)])
        )
    except ProviderCliError as exc:
        _handle_error(exc)


@vm_app.command("terminate")
def vm_terminate(
    vm_id: str,
    yes: bool = typer.Option(False, "--yes", "-y", help="Do not prompt."),
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Terminate a VM lease as the provider."""
    try:
        _confirm(f"Terminate lease for VM {vm_id}?", yes)
        result = _client(api, token).post(f"/admin/vms/{vm_id}/terminate-lease")
        output(result, json_out=json_out, title="Lease Termination")
    except ProviderCliError as exc:
        _handle_error(exc)


@stream_app.command("list")
def stream_list(
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """List payment streams."""
    try:
        rows = _client(api, token).get("/payments/streams")
        output(rows, json_out=json_out, title="Streams")
    except ProviderCliError as exc:
        _handle_error(exc)


@stream_app.command("show")
def stream_show(
    vm_id: str,
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Show one VM's stream."""
    try:
        output(
            _client(api, token).get(f"/vms/{vm_id}/stream"),
            json_out=json_out,
            title="Stream",
        )
    except ProviderCliError as exc:
        _handle_error(exc)


@stream_app.command("earnings")
def stream_earnings(
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Summarize stream earnings."""
    try:
        streams = _client(api, token).get("/payments/streams")
        totals = {
            "streams": len(streams),
            "vested_wei": sum(
                int((item.get("computed") or {}).get("vested_wei") or 0)
                for item in streams
            ),
            "withdrawable_wei": sum(
                int((item.get("computed") or {}).get("withdrawable_wei") or 0)
                for item in streams
            ),
        }
        output({"totals": totals, "streams": streams}, json_out=json_out)
    except ProviderCliError as exc:
        _handle_error(exc)


@stream_app.command("withdraw")
def stream_withdraw(
    vm_id: Optional[str] = typer.Argument(None, help="VM id to withdraw."),
    all_streams: bool = typer.Option(False, "--all", help="Withdraw all streams."),
):
    """Withdraw stream funds using the existing provider wallet flow."""
    if not vm_id and not all_streams:
        typer.echo("Specify a VM id or --all", err=True)
        raise typer.Exit(code=1)
    from provider.main import streams_withdraw

    streams_withdraw(vm_id=vm_id, all_streams=all_streams)


@monitor_app.callback()
def monitor(
    ctx: typer.Context,
    watch: bool = typer.Option(False, "--watch", help="Refresh continuously."),
    count: Optional[int] = typer.Option(None, "--count", help="Number of refreshes."),
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Show host monitoring data."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        client = _client(api, token)
        iterations = 0
        while True:
            data = client.get("/monitoring/metrics/latest")
            output(data, json_out=json_out, title="Monitoring")
            iterations += 1
            if count is not None and iterations >= count:
                return
            if not watch:
                return
            time.sleep(2)
    except ProviderCliError as exc:
        _handle_error(exc)


@monitor_app.command("history")
def monitor_history(
    range: str = typer.Option("1h", "--range", help="History range."),
    metric: Optional[str] = typer.Option(None, "--metric", help="Metric to print."),
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Show host metric history."""
    try:
        data = _client(api, token).get(
            "/monitoring/metrics/history", params={"range": range}
        )
        if metric and not json_out:
            data = [
                point
                for point in data.get("points", [])
                if point.get("metric") == metric
            ]
        output(data, json_out=json_out, title="Metric History")
    except ProviderCliError as exc:
        _handle_error(exc)


@monitor_app.command("vm")
def monitor_vm(
    vm_id: str,
    range: Optional[str] = typer.Option(None, "--range", help="History range."),
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Show VM monitoring data."""
    try:
        client = _client(api, token)
        if range:
            data = client.get(f"/vms/{vm_id}/metrics/history", params={"range": range})
        else:
            data = client.get(f"/vms/{vm_id}/metrics/latest")
        output(data, json_out=json_out, title="VM Metrics")
    except ProviderCliError as exc:
        _handle_error(exc)


@alert_app.command("list")
def alert_list(
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """List active alerts."""
    try:
        output(_client(api, token).get("/monitoring/alerts"), json_out=json_out)
    except ProviderCliError as exc:
        _handle_error(exc)


@alert_app.command("rules")
def alert_rules(
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """List alert rules."""
    try:
        output(_client(api, token).get("/monitoring/alert-rules"), json_out=json_out)
    except ProviderCliError as exc:
        _handle_error(exc)


@alert_app.command("add")
def alert_add(
    name: str = typer.Option(..., "--name", help="Rule name."),
    metric: str = typer.Option(..., "--metric", help="Metric name."),
    scope: str = typer.Option(..., "--scope", help="host or vm."),
    source: str = typer.Option(..., "--source", help="infrastructure or guest_agent."),
    operator: str = typer.Option(..., "--op", help="Comparison operator."),
    threshold: float = typer.Option(..., "--threshold", help="Threshold."),
    duration: int = typer.Option(..., "--for", help="Duration in seconds."),
    severity: str = typer.Option("warning", "--severity", help="warning or critical."),
    disabled: bool = typer.Option(False, "--disabled", help="Create disabled."),
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Create an alert rule."""
    try:
        payload = {
            "id": None,
            "name": name,
            "metric": metric,
            "scope": scope,
            "source": source,
            "operator": operator,
            "threshold": threshold,
            "duration_seconds": duration,
            "severity": severity,
            "enabled": not disabled,
        }
        output(
            _client(api, token).post("/monitoring/alert-rules", json_body=payload),
            json_out=json_out,
            title="Alert Rule",
        )
    except ProviderCliError as exc:
        _handle_error(exc)


@webhook_app.command("list")
def webhook_list(
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """List webhooks."""
    try:
        output(_client(api, token).get("/monitoring/webhooks"), json_out=json_out)
    except ProviderCliError as exc:
        _handle_error(exc)


@webhook_app.command("show")
def webhook_show(
    webhook_id: int,
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Show one webhook and recent deliveries."""
    try:
        client = _client(api, token)
        webhook = _find_webhook(client, webhook_id)
        deliveries = client.get(f"/monitoring/webhooks/{webhook_id}/deliveries")
        output(
            {"webhook": webhook, "deliveries": deliveries},
            json_out=json_out,
            title="Webhook",
        )
    except ProviderCliError as exc:
        _handle_error(exc)


@webhook_app.command("add")
def webhook_add(
    name: str = typer.Option(..., "--name", help="Webhook name."),
    url: str = typer.Option(..., "--url", help="Webhook URL."),
    service: str = typer.Option("generic_json", "--service", help="Service type."),
    event: list[str] = typer.Option(..., "--event", help="Event to send."),
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Create a webhook."""
    try:
        payload = _webhook_payload(name=name, url=url, service=service, events=event)
        output(
            _client(api, token).post("/monitoring/webhooks", json_body=payload),
            json_out=json_out,
            title="Webhook",
        )
    except ProviderCliError as exc:
        _handle_error(exc)


@webhook_app.command("edit")
def webhook_edit(
    webhook_id: int,
    name: Optional[str] = typer.Option(None, "--name", help="Webhook name."),
    url: Optional[str] = typer.Option(None, "--url", help="Webhook URL."),
    service: Optional[str] = typer.Option(None, "--service", help="Service type."),
    event: Optional[list[str]] = typer.Option(None, "--event", help="Event to send."),
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Update a webhook."""
    try:
        client = _client(api, token)
        payload = _find_webhook(client, webhook_id)
        if name is not None:
            payload["name"] = name
        if url is not None:
            payload["url"] = url
        if service is not None:
            payload["service_type"] = service
        if event is not None:
            payload["events"] = event
        output(
            client.put(f"/monitoring/webhooks/{webhook_id}", json_body=payload),
            json_out=json_out,
            title="Webhook",
        )
    except ProviderCliError as exc:
        _handle_error(exc)


@webhook_app.command("enable")
def webhook_enable(
    webhook_id: int,
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Enable a webhook."""
    _set_webhook_enabled(webhook_id, True, api, token)


@webhook_app.command("disable")
def webhook_disable(
    webhook_id: int,
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Disable a webhook."""
    _set_webhook_enabled(webhook_id, False, api, token)


@webhook_app.command("delete")
def webhook_delete(
    webhook_id: int,
    yes: bool = typer.Option(False, "--yes", "-y", help="Do not prompt."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Delete a webhook."""
    try:
        _confirm(f"Delete webhook {webhook_id}?", yes)
        _client(api, token).delete(f"/monitoring/webhooks/{webhook_id}")
        typer.echo(f"Deleted webhook {webhook_id}")
    except ProviderCliError as exc:
        _handle_error(exc)


@webhook_app.command("test")
def webhook_test(
    webhook_id: int,
    event: str = typer.Option("alert.fired", "--event", help="Event type."),
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Send a test webhook delivery."""
    try:
        output(
            _client(api, token).post(
                f"/monitoring/webhooks/{webhook_id}/test",
                json_body={"event_type": event},
            ),
            json_out=json_out,
            title="Webhook Test",
        )
    except ProviderCliError as exc:
        _handle_error(exc)


@webhook_app.command("deliveries")
def webhook_deliveries(
    webhook_id: int,
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """List webhook delivery attempts."""
    try:
        output(
            _client(api, token).get(f"/monitoring/webhooks/{webhook_id}/deliveries"),
            json_out=json_out,
            title="Webhook Deliveries",
        )
    except ProviderCliError as exc:
        _handle_error(exc)


@settings_app.callback()
def settings(
    ctx: typer.Context,
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Show provider settings."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        output(_client(api, token).get("/provider/settings"), json_out=json_out)
    except ProviderCliError as exc:
        _handle_error(exc)


settings_app.add_typer(settings_resources_app, name="resources")
settings_app.add_typer(settings_pricing_app, name="pricing")


@settings_resources_app.callback()
def settings_resources(
    ctx: typer.Context,
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Show provider resource settings."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        data = _client(api, token).get("/provider/settings")
        output(
            {
                key: data.get(key)
                for key in (
                    "detected_resources",
                    "offered_resources",
                    "allocated_resources",
                    "available_resources",
                    "minimum_configurable_resources",
                )
            },
            json_out=json_out,
            title="Resources",
        )
    except ProviderCliError as exc:
        _handle_error(exc)


@settings_resources_app.command("set")
def settings_resources_set(
    cpu: int = typer.Option(..., "--cpu", help="Offered CPU cores."),
    memory: int = typer.Option(..., "--memory", help="Offered RAM in GB."),
    storage: int = typer.Option(..., "--storage", help="Offered storage in GB."),
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Set offered provider resources."""
    try:
        output(
            _client(api, token).patch(
                "/provider/settings/resources",
                json_body={"cpu": cpu, "memory": memory, "storage": storage},
            ),
            json_out=json_out,
            title="Resources",
        )
    except ProviderCliError as exc:
        _handle_error(exc)


@settings_pricing_app.callback()
def settings_pricing(
    ctx: typer.Context,
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Show provider pricing settings."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        data = _client(api, token).get("/provider/settings")
        output(data.get("pricing") or {}, json_out=json_out, title="Pricing")
    except ProviderCliError as exc:
        _handle_error(exc)


@settings_pricing_app.command("set")
def settings_pricing_set(
    cpu: float = typer.Option(..., "--cpu", help="USD per CPU core month."),
    memory: float = typer.Option(..., "--memory", help="USD per GB RAM month."),
    storage: float = typer.Option(..., "--storage", help="USD per GB storage month."),
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Set provider USD pricing."""
    try:
        output(
            _client(api, token).patch(
                "/provider/settings/pricing",
                json_body={
                    "usd_per_core_month": cpu,
                    "usd_per_gb_ram_month": memory,
                    "usd_per_gb_storage_month": storage,
                },
            ),
            json_out=json_out,
            title="Pricing",
        )
    except ProviderCliError as exc:
        _handle_error(exc)


@settings_pricing_app.command("calc")
def settings_pricing_calc(
    cpu: int = typer.Option(..., "--cpu", help="CPU cores."),
    memory: int = typer.Option(..., "--memory", help="RAM in GB."),
    storage: int = typer.Option(..., "--storage", help="Storage in GB."),
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
    api: str = typer.Option(DEFAULT_API_BASE_URL, "--api", help="Provider API URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Provider admin token."),
):
    """Estimate monthly VM pricing from current settings."""
    try:
        pricing = _client(api, token).get("/provider/settings").get("pricing") or {}
        monthly_usd = (
            cpu * float(pricing.get("usd_per_core_month") or 0)
            + memory * float(pricing.get("usd_per_gb_ram_month") or 0)
            + storage * float(pricing.get("usd_per_gb_storage_month") or 0)
        )
        monthly_glm = (
            cpu * float(pricing.get("glm_per_core_month") or 0)
            + memory * float(pricing.get("glm_per_gb_ram_month") or 0)
            + storage * float(pricing.get("glm_per_gb_storage_month") or 0)
        )
        output(
            {
                "resources": {"cpu": cpu, "memory": memory, "storage": storage},
                "monthly_usd": round(monthly_usd, 4),
                "monthly_glm": round(monthly_glm, 6),
            },
            json_out=json_out,
            title="Pricing Estimate",
        )
    except ProviderCliError as exc:
        _handle_error(exc)


def root_info(
    json_out: bool,
    api: str,
    token: Optional[str],
) -> None:
    try:
        output(_client(api, token).get("/provider/info"), json_out=json_out)
    except ProviderCliError as exc:
        _handle_error(exc)


def root_summary(
    json_out: bool,
    api: str,
    token: Optional[str],
) -> None:
    try:
        output(_client(api, token).get("/summary"), json_out=json_out)
    except ProviderCliError as exc:
        _handle_error(exc)


def root_metrics(
    api: str,
    token: Optional[str],
) -> None:
    try:
        url = f"{api.rstrip('/')}/metrics"
        import httpx

        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token or ProviderAdminClient().token}"},
            timeout=10.0,
        )
        if response.status_code in (401, 403):
            raise ProviderCliError(
                "Provider admin token was rejected by the running provider."
            )
        if response.status_code >= 400:
            raise ProviderCliError(f"Provider API returned HTTP {response.status_code}")
        typer.echo(response.text)
    except ProviderCliError as exc:
        _handle_error(exc)


def root_watch(
    api: str,
    token: Optional[str],
    count: Optional[int] = None,
) -> None:
    try:
        client = _client(api, token)
        iterations = 0
        while True:
            summary = client.get("/summary")
            print_mapping(summary, title="Provider Summary")
            iterations += 1
            if count is not None and iterations >= count:
                return
            time.sleep(2)
    except ProviderCliError as exc:
        _handle_error(exc)


def _find_webhook(client: ProviderAdminClient, webhook_id: int) -> dict[str, Any]:
    for webhook in client.get("/monitoring/webhooks"):
        if webhook.get("id") == webhook_id:
            return webhook
    raise ProviderCliError(f"Webhook {webhook_id} was not found.")


def _set_webhook_enabled(
    webhook_id: int,
    enabled: bool,
    api: str,
    token: Optional[str],
) -> None:
    try:
        client = _client(api, token)
        payload = _find_webhook(client, webhook_id)
        payload["enabled"] = enabled
        client.put(f"/monitoring/webhooks/{webhook_id}", json_body=payload)
        typer.echo(f"{'Enabled' if enabled else 'Disabled'} webhook {webhook_id}")
    except ProviderCliError as exc:
        _handle_error(exc)


def _webhook_payload(
    *,
    name: str,
    url: str,
    service: str,
    events: list[str],
) -> dict[str, Any]:
    return {
        "id": None,
        "name": name,
        "url": url,
        "enabled": True,
        "service_type": service,
        "events": events,
        "template": {
            "title": "{{summary}}",
            "message": "{{summary}}",
            "color": "severity",
            "fields": [
                {"name": "Event", "value": "{{event.type}}"},
                {"name": "Resource", "value": "{{resource.id}}"},
                {"name": "Severity", "value": "{{severity}}"},
            ],
            "footer": "Golem Provider",
        },
        "last_status": None,
        "last_http_status": None,
        "last_error": None,
        "last_delivered_at": None,
    }
