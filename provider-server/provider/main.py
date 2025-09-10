import asyncio
import os
import sys as _sys
import socket
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from .utils.logging import setup_logger


# If the invocation includes --json, mute logs as early as possible
if "--json" in _sys.argv:
    os.environ["GOLEM_SILENCE_LOGS"] = "1"

# Defer heavy local imports (may import config) until after we decide on silence
from .container import Container
from .service import ProviderService

logger = setup_logger(__name__)

app = FastAPI(title="VM on Golem Provider")
container = Container()
app.container = container
container.wire(modules=[".api.routes"])

# Minimal safe defaults so DI providers that rely on config have paths before runtime
try:
    from pathlib import Path as _Path
    container.config.from_dict({
        "VM_DATA_DIR": str(_Path.home() / ".golem" / "provider" / "vms"),
        "PROXY_STATE_DIR": str(_Path.home() / ".golem" / "provider" / "proxy"),
        "PORT_RANGE_START": 50800,
        "PORT_RANGE_END": 50900,
        "PORT": 7466,
        "SKIP_PORT_VERIFICATION": True,
    })
except Exception:
    pass

from .vm.models import VMNotFoundError
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(VMNotFoundError)
async def vm_not_found_exception_handler(request: Request, exc: VMNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"message": str(exc)},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred"},
    )

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.on_event("startup")
async def startup_event():
    """Handle application startup."""
    # Load configuration into container lazily at runtime
    from .config import settings as _settings
    try:
        container.config.from_dict(_settings.model_dump())
    except Exception:
        # Fallback for environments without pydantic v2 model_dump
        container.config.from_pydantic(_settings)
    provider_service = container.provider_service()
    await provider_service.setup(app)


@app.on_event("shutdown")
async def shutdown_event():
    """Handle application shutdown."""
    provider_service = container.provider_service()
    await provider_service.cleanup()

# Import routes after app creation to avoid circular imports
from .api import routes
app.include_router(routes.router, prefix="/api/v1")

# Export app for uvicorn
__all__ = ["app", "start"]


def check_requirements():
    """Check if all requirements are met."""
    try:
        # Import settings to trigger validation
        from .config import settings
        return True
    except Exception as e:
        logger.error(f"Requirements check failed: {e}")
        return False


async def verify_provider_port(port: int) -> bool:
    """Verify that the provider port is available for binding.

    Args:
        port: The port to verify

    Returns:
        bool: True if the port is available, False otherwise
    """
    try:
        # Try to create a temporary listener
        server = await asyncio.start_server(
            lambda r, w: None,  # Empty callback
            '0.0.0.0',
            port
        )
        server.close()
        await server.wait_closed()
        logger.info(f"✅ Provider port {port} is available")
        return True
    except Exception as e:
        logger.error(f"❌ Provider port {port} is not available: {e}")
        logger.error("Please ensure:")
        logger.error(f"1. Port {port} is not in use by another application")
        logger.error("2. You have permission to bind to this port")
        logger.error("3. Your firewall allows binding to this port")
        return False


# The get_local_ip function has been removed as this logic is now handled in config.py


import typer
try:
    from importlib import metadata
except ImportError:
    # Python < 3.8
    import importlib_metadata as metadata

cli = typer.Typer()
pricing_app = typer.Typer(help="Configure USD pricing; auto-converts to GLM.")
wallet_app = typer.Typer(help="Wallet utilities (funding, balance)")
streams_app = typer.Typer(help="Inspect payment streams")
cli.add_typer(pricing_app, name="pricing")
cli.add_typer(wallet_app, name="wallet")
cli.add_typer(streams_app, name="streams")
config_app = typer.Typer(help="Configure stream monitoring and withdrawals")
cli.add_typer(config_app, name="config")

@cli.callback()
def main(ctx: typer.Context):
    """VM on Golem Provider CLI"""
    # No-op callback to initialize config; avoid custom --version flag to keep help stable
    return


def _get_installed_version(pkg_name: str) -> str:
    try:
        return metadata.version(pkg_name)
    except Exception:
        return "unknown"


def _get_latest_version_from_pypi(pkg_name: str) -> Optional[str]:
    # Avoid network in pytest runs
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    try:
        import json as _json
        from urllib.request import urlopen
        with urlopen(f"https://pypi.org/pypi/{pkg_name}/json", timeout=5) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
            return data.get("info", {}).get("version")
    except Exception:
        return None


@cli.command("status")
def status(json_out: bool = typer.Option(False, "--json", help="Output machine-readable JSON")):
    """Show provider environment status and update info (pretty or JSON)."""
    from .utils.logging import logger as _logger
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    # For JSON, set a process-wide mute env that setup_logger() respects
    import os as _os
    if json_out:
        _os.environ["GOLEM_SILENCE_LOGS"] = "1"

    # Temporarily quiet logs; when --json, suppress near everything
    prev_level = _logger.level
    import logging as _logging
    _root_logger = _logging.getLogger()
    _prev_root_level = _root_logger.level
    try:
        _logger.setLevel("WARNING")
        if json_out:
            _root_logger.setLevel(_logging.CRITICAL)
    except Exception:
        pass

    # Silence port_verifier warnings during status checks for clean UI
    try:
        _pv_logger = _logging.getLogger("provider.network.port_verifier")
        _prev_pv_level = _pv_logger.level
        _pv_logger.setLevel(_logging.CRITICAL)
    except Exception:
        _pv_logger = None
        _prev_pv_level = None
    # Also quiet config auto-detection logs (e.g., multipass path) for clean JSON/TTY
    try:
        _cfg_logger = _logging.getLogger("provider.config")
        _prev_cfg_level = _cfg_logger.level
        _cfg_logger.setLevel(_logging.WARNING)
    except Exception:
        _cfg_logger = None
        _prev_cfg_level = None

    # Defer config-heavy imports until after log levels are adjusted
    from .config import settings as _settings
    from .network.port_verifier import PortVerifier

    # Versions
    pkg = "golem-vm-provider"
    current = _get_installed_version(pkg)
    latest = _get_latest_version_from_pypi(pkg)
    update_available = bool(latest and current != latest)

    # Environment
    env = os.environ.get("GOLEM_PROVIDER_ENVIRONMENT", _settings.ENVIRONMENT)
    net = getattr(_settings, "NETWORK", None)
    dev_mode = env == "development" or bool(getattr(_settings, "DEV_MODE", False))

    # Multipass
    mp = {"ok": False, "path": None, "version": None, "error": None}
    try:
        mp_path = _settings.MULTIPASS_BINARY_PATH
        mp["path"] = mp_path or None
        if mp_path:
            import subprocess
            r = subprocess.run([mp_path, "version"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                mp["ok"] = True
                mp["version"] = (r.stdout or r.stderr).strip()
            else:
                mp["error"] = (r.stderr or r.stdout or "failed").strip()
        else:
            mp["error"] = "not configured"
    except Exception as e:
        mp["ok"] = False
        mp["error"] = str(e)

    # Provider port (local)
    port = int(_settings.PORT)
    host = getattr(_settings, "HOST", "0.0.0.0")
    local = {"ok": False, "detail": None}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        local_conn = s.connect_ex(("127.0.0.1", port)) == 0
        s.close()
        if local_conn:
            local["ok"] = True
            local["detail"] = "service is listening"
        else:
            # Check that we can bind (port free)
            if asyncio.run(verify_provider_port(port)):
                local["ok"] = True
                local["detail"] = "port is free (bindable)"
            else:
                local["ok"] = False
                local["detail"] = "port unavailable"
    except Exception as e:
        local["ok"] = False
        local["detail"] = str(e)

    # Always use shared external port-checker for public reachability
    servers = ["http://195.201.39.101:9000"]

    external = {"status": "unknown", "verified_by": None, "error": None}
    try:
        verifier = PortVerifier(servers, discovery_port=port)
        results = asyncio.run(verifier.verify_external_access({port}))
        r = results.get(port)
        if r and r.accessible:
            external["status"] = "reachable"
            external["verified_by"] = r.verified_by
        elif r:
            external["status"] = "unreachable"
            external["error"] = r.error
        else:
            external["status"] = "not_verified"
    except Exception as e:
        external["status"] = "check_failed"
        external["error"] = str(e).splitlines()[0]

    # Base data structure
    data = {
        "version": {
            "installed": current,
            "latest": latest,
            "update_available": update_available,
        },
        "environment": {
            "environment": env,
            "network": net,
            "dev_mode": dev_mode,
        },
        "multipass": mp,
        "ports": {
            "provider": {
                "port": port,
                "host": host,
                "local_ok": local["ok"],
                "local_detail": local["detail"],
                "external": external,
            }
        },
    }

    # SSH port usage summary from state file + external reachability for full range
    try:
        from pathlib import Path as _Path
        import json as _json
        state_path = _Path(_settings.PROXY_STATE_DIR) / "ports.json"
        ports_in_use = []
        if state_path.exists():
            with open(state_path, "r") as fh:
                st = _json.load(fh)
            for _req_name, pinfo in (st.get("proxies", {}) or {}).items():
                prt = pinfo.get("port")
                if isinstance(prt, int):
                    ports_in_use.append(prt)
        start = int(getattr(_settings, "PORT_RANGE_START", 50800))
        end = int(getattr(_settings, "PORT_RANGE_END", 50900))
        total = max(0, end - start)
        used = sorted(set(prt for prt in ports_in_use if start <= prt < end))
        # Check if used ports are actually listening
        used_listening = []
        used_not_listening = []
        for prt in used:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                ok = s.connect_ex(("127.0.0.1", prt)) == 0
                s.close()
                (used_listening if ok else used_not_listening).append(prt)
            except Exception:
                used_not_listening.append(prt)
        free_count = total - len(used)
        # External reachability across entire range
        external_ok: set[int] = set()
        ext_results_map: dict[int, bool] = {}
        external_batch_ok = False
        external_batch_error: str | None = None
        try:
            verifier_all = PortVerifier(servers, discovery_port=port)
            _ext_results = asyncio.run(verifier_all.verify_external_access(set(range(start, end))))
            for prt, res in _ext_results.items():
                p = int(prt)
                ok = bool(getattr(res, "accessible", False))
                ext_results_map[p] = ok
                if ok:
                    external_ok.add(p)
            external_batch_ok = True
        except Exception:
            # Leave external_ok empty on failure
            external_batch_ok = False
            try:
                external_batch_error = str(_)  # type: ignore[name-defined]
            except Exception:
                external_batch_error = None

        firewall_issues = [p for p in used_listening if p not in external_ok]

        # Build per-port details for JSON consumers
        details = []
        for p in range(start, end):
            details.append({
                "port": p,
                "in_use": p in used,
                "local_listening": p in used_listening,
                "external_reachable": bool(ext_results_map.get(p, False)) if external_batch_ok else False,
            })

        # Compute number of free ports that are actually externally reachable (usable)
        usable_free_count = None
        try:
            if external_batch_ok:
                usable_free_count = len([
                    p for p in range(start, end)
                    if (p not in used) and bool(ext_results_map.get(p, False))
                ])
        except Exception:
            usable_free_count = None

        # Legacy detailed metrics (retained under ssh_legacy)
        _ssh_legacy = {
            "range": [start, end],
            "total": total,
            "in_use": used,
            "listening_ok": used_listening,
            "listening_issues": used_not_listening,
            "free_count": free_count,
            "external_reachable_count": len([p for p in range(start, end) if p in external_ok]),
            "firewall_issues_count": len(firewall_issues),
            "external_checked": external_batch_ok,
            "external_error": external_batch_error,
            "usable_free_count": usable_free_count,
            "details": details,
        }

        # Concise status fields for programmatic checks (mirrors TTY)
        _ext_reach = int(len(external_ok))
        _issues_count = len(used_not_listening) + len(firewall_issues)
        if (not external_batch_ok) or _ext_reach == 0:
            ssh_status = "blocked"
        elif _issues_count > 0:
            ssh_status = "limited"
        else:
            ssh_status = "ok"

        # Usable free: default to 0 when external check failed
        if usable_free_count is None:
            usable_free_out = 0
        else:
            usable_free_out = int(usable_free_count)

        # Issues breakdown matching TTY wording
        unreachable_count = total if (not external_batch_ok or _ext_reach == 0) else len(firewall_issues)
        not_listening_count = len(used_not_listening)

        # Build minimal per-port status list for JSON consumers
        # Consistent definition:
        # - status: reachable | unreachable | unknown (unknown only if external check failed)
        # - listening: true | false
        ports_detail: list[dict] = []
        for p in range(start, end):
            listening = p in used_listening
            if external_batch_ok:
                status_val = "reachable" if bool(ext_results_map.get(p, False)) else "unreachable"
            else:
                status_val = "unknown"
            ports_detail.append({
                "port": p,
                "status": status_val,
                "listening": bool(listening),
            })

        data["ports"]["ssh"] = {
            "range": [start, end],
            "status": ssh_status,
            "usable_free": usable_free_out,
            "in_use": len(used),
            "issues": {
                "unreachable": int(unreachable_count),
                "not_listening": int(not_listening_count),
            },
            "ports": ports_detail,
        }

    except Exception:
        # Non-fatal; omit ssh summary if state not available
        pass

    # Provider concise status: reachable | unreachable (treat check failures as unreachable)
    prov_status = external.get("status")
    provider_status = "reachable" if prov_status == "reachable" else "unreachable"
    data["ports"]["provider"]["status"] = provider_status

    # Compute overall and issues for JSON output (mirrors condensed model)
    json_issues = []
    json_ssh_blocked = False
    json_critical_no_ssh = False
    # Multipass
    if not mp["ok"]:
        json_issues.append("Multipass not available")
    # Provider local port
    if not local["ok"]:
        json_issues.append(f"Provider port {port} not ready")
    # SSH ports
    if data["ports"].get("ssh"):
        _ssh = data["ports"]["ssh"]
        _status = str(_ssh.get("status") or "blocked").lower()
        _issues = _ssh.get("issues") or {}
        _not_listening = int(_issues.get("not_listening", 0) or 0)
        _unreachable = int(_issues.get("unreachable", 0) or 0)
        if _status == "blocked":
            json_ssh_blocked = True
            json_critical_no_ssh = True
            json_issues.append("No externally reachable SSH ports")
        else:
            if _unreachable > 0:
                json_issues.append(f"{_unreachable} SSH port(s) unreachable externally")
        if _not_listening > 0:
            json_issues.append(f"{_not_listening} SSH port(s) not listening")
    # Provider external
    json_critical_provider_external = False
    if external.get("status") in ("unreachable", "check_failed"):
        json_issues.append("Provider API port not reachable externally")
        json_critical_provider_external = True

    if json_critical_no_ssh or (not local["ok"]) or (not mp["ok"]) or json_critical_provider_external:
        overall_status = "error"
    else:
        overall_status = "healthy" if (not json_issues and not json_ssh_blocked) else "issues"

    data["overall"] = {"status": overall_status, "issues": json_issues}

    if json_out:
        import json as _json
        print(_json.dumps(data, indent=2))
        # Restore logger level
        try:
            _logger.setLevel(prev_level)
        except Exception:
            pass
        if _pv_logger and _prev_pv_level is not None:
            try:
                _pv_logger.setLevel(_prev_pv_level)
            except Exception:
                pass
        if _cfg_logger and _prev_cfg_level is not None:
            try:
                _cfg_logger.setLevel(_prev_cfg_level)
            except Exception:
                pass
        # Restore root logger
        try:
            _root_logger.setLevel(_prev_root_level)
        except Exception:
            pass
        # Restore root logger
        try:
            _root_logger.setLevel(_prev_root_level)
        except Exception:
            pass
        # Unset mute env if we set it
        if json_out:
            try:
                del _os.environ["GOLEM_SILENCE_LOGS"]
            except Exception:
                pass
        return

    console = Console()

    # Overall status
    issues = []
    if not mp["ok"]:
        issues.append("Multipass not available")
    if not local["ok"]:
        issues.append(f"Provider port {port} not ready")
    ssh_blocked = False
    critical_no_ssh = False
    if data["ports"].get("ssh"):
        ssh = data["ports"]["ssh"]
        if ssh.get("listening_issues"):
            issues.append(f"{len(ssh['listening_issues'])} SSH port(s) not listening")
        if ssh.get("free_count", 0) == 0:
            issues.append("No free SSH ports available")
        if ssh.get("external_checked"):
            if int(ssh.get("external_reachable_count", 0) or 0) == 0:
                ssh_blocked = True
                critical_no_ssh = True  # No externally reachable SSH ports is critical
                issues.append("No externally reachable SSH ports")
        else:
            # If we couldn't check, mark as issue but not critical
            issues.append("SSH external reachability check failed")
    critical_provider_external = False
    if external["status"] in ("unreachable", "check_failed"):
        issues.append("Provider API port not reachable externally")
        critical_provider_external = True

    # Severity: Error when critical conditions are met; else Issues/Healthy
    if critical_no_ssh or (not local["ok"]) or (not mp["ok"]) or critical_provider_external:
        overall = "Error"
    else:
        overall = "Healthy" if (not issues and not ssh_blocked) else "Issues detected"

    # Build a single compact table
    tbl = Table(box=box.SIMPLE_HEAVY, show_header=False, pad_edge=False)
    tbl.add_column("Item", style="bold")
    tbl.add_column("Value")

    # Header
    if overall == "Healthy":
        overall_txt = "[green]Healthy[/green]"
    elif overall == "Error":
        overall_txt = "[red]Error[/red]"
    else:
        overall_txt = f"[yellow]{overall}[/yellow]"
    tbl.add_row("Overall", overall_txt)
    tbl.add_row("", "")

    # Versions
    tbl.add_row("Versions", "")
    ver_inst = data["version"]["installed"] or "unknown"
    ver_latest = data["version"]["latest"] or "unknown"
    upd = data["version"]["update_available"]
    tbl.add_row("  Installed", f"[white]{ver_inst}[/white]")
    if upd:
        tbl.add_row("  Latest", f"[bold bright_yellow]{ver_latest}[/bold bright_yellow]  [grey62](pip install -U golem-vm-provider)[/grey62]")
        tbl.add_row("  Update", "[bold bright_yellow]⬆️  yes[/bold bright_yellow]")
    else:
        tbl.add_row("  Latest", f"[cyan]{ver_latest}[/cyan]")
        tbl.add_row("  Update", "[green]no[/green]")
    tbl.add_row("", "")

    # Environment
    tbl.add_row("Environment", "")
    tbl.add_row("  Environment", env + (" (dev)" if dev_mode else ""))
    tbl.add_row("  Network", net or "-")
    tbl.add_row("", "")

    # Multipass
    mp_ver = (mp.get("version") or mp.get("error") or "-").replace("\n", ", ")
    tbl.add_row("Multipass", "")
    tbl.add_row("  Status", "✅ OK" if mp["ok"] else "❌ Missing")
    tbl.add_row("  Path", mp.get("path") or "-")
    tbl.add_row("  Version", mp_ver)
    tbl.add_row("", "")

    # Provider port
    tbl.add_row("Provider Port", f"{host}:{port}")
    tbl.add_row("  Local", ("✅ " if local["ok"] else "❌ ") + (local["detail"] or ""))
    # External reachability is foundational; treat unreachable and check failures the same
    _ext = external.get("status") or "unknown"
    _err = external.get("error")
    if _ext == "reachable":
        ext_row = "✅ reachable"
    elif _ext in ("unreachable", "check_failed"):
        ext_row = "❌ unreachable" + (f" — {_err}" if _err else "")
    elif _ext == "not_verified":
        ext_row = "⚠️ not verified"
    else:
        ext_row = "⚠️ " + _ext + (f" — {_err}" if _err else "")
    tbl.add_row("  External", ext_row)

    # SSH ports (condensed, actionable)
    if data["ports"].get("ssh"):
        ssh = data["ports"]["ssh"]
        r0, r1 = ssh['range'][0], ssh['range'][1]-1
        tbl.add_row("", "")
        status_val = str(ssh.get("status") or "blocked").lower()
        issues_obj = ssh.get("issues") or {}
        unreachable_issues = int(issues_obj.get("unreachable", 0) or 0)
        not_listening_issues = int(issues_obj.get("not_listening", 0) or 0)
        in_use = int(ssh.get("in_use", 0) or 0)
        usable_free = ssh.get("usable_free")

        # Determine clear status
        if status_val == "ok":
            status_txt = "[green]OK[/green]"
        elif status_val == "limited":
            status_txt = f"[yellow]limited — {not_listening_issues + (unreachable_issues or 0)} issue(s)[/yellow]"
        else:
            status_txt = "[red]blocked[/red]"

        tbl.add_row("SSH Ports", f"{r0}-{r1} — {status_txt}")

        # Provide only the most relevant numbers
        # Usable free = free and externally reachable; avoid misleading "Free" when blocked
        tbl.add_row("  Usable free", str(int(usable_free or 0)))
        tbl.add_row("  In use", str(in_use))
        if status_val == "blocked":
            # Show total not reachable externally
            total_ports = (r1 - r0 + 1)
            cnt = unreachable_issues if unreachable_issues else total_ports
            tbl.add_row("  Issues", f"{cnt} not reachable externally")
        elif (not_listening_issues or unreachable_issues):
            parts = []
            if unreachable_issues:
                parts.append(f"{unreachable_issues} unreachable (listening but blocked)")
            if not_listening_issues:
                parts.append(f"{not_listening_issues} not listening")
            tbl.add_row("  Issues", ", ".join(parts))

    # Issues / Tips combined at bottom
    # Only show Notes when there are issues
    if issues:
        tbl.add_row("", "")
        tbl.add_row("Issues", "\n".join(f"• {t}" for t in issues))

    console.print(Panel(tbl, title="Provider Status"))

    # Tips
    tips = []
    if update_available:
        tips.append("Upgrade with: pip install -U golem-vm-provider")
    if not mp["ok"]:
        tips.append("Install Multipass and/or set GOLEM_PROVIDER_MULTIPASS_BINARY_PATH")
    if external["status"] != "reachable":
        tips.append("Ensure at least one port-check server is online (see above)")
    # Tips are included in the single panel under Notes

    # Restore logger level
    try:
        _logger.setLevel(prev_level)
    except Exception:
        pass
    if _pv_logger and _prev_pv_level is not None:
        try:
            _pv_logger.setLevel(_prev_pv_level)
        except Exception:
            pass
    if _cfg_logger and _prev_cfg_level is not None:
        try:
            _cfg_logger.setLevel(_prev_cfg_level)
        except Exception:
            pass
    try:
        _root_logger.setLevel(_prev_root_level)
    except Exception:
        pass
    # Unset mute env if we set it
    if json_out:
        try:
            del _os.environ["GOLEM_SILENCE_LOGS"]
        except Exception:
            pass


@wallet_app.command("faucet-l2")
def wallet_faucet_l2():
    """Request L2 faucet funds for the provider's payment address (native ETH)."""
    from .config import settings
    from .security.l2_faucet import L2FaucetService
    try:
        if not bool(getattr(settings, "FAUCET_ENABLED", False)):
            print("Faucet is disabled for current payments network.")
            raise typer.Exit(code=0)
        addr = settings.PROVIDER_ID
        async def _run():
            svc = L2FaucetService(settings)
            tx = await svc.request_funds(addr)
            if tx:
                print(f"Faucet tx: {tx}")
            else:
                # Either skipped due to sufficient balance or failed
                pass
        asyncio.run(_run())
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(code=1)


@streams_app.command("list")
def streams_list(json_out: bool = typer.Option(False, "--json", help="Output in JSON")):
    """List all mapped streams with computed status."""
    from .container import Container
    from .config import settings
    from .payments.blockchain_service import StreamPaymentReader
    from .utils.pricing import fetch_glm_usd_price, fetch_eth_usd_price
    from decimal import Decimal
    from web3 import Web3
    import json as _json
    try:
        if json_out:
            os.environ["GOLEM_SILENCE_LOGS"] = "1"
        if not settings.STREAM_PAYMENT_ADDRESS or settings.STREAM_PAYMENT_ADDRESS == "0x0000000000000000000000000000000000000000":
            if json_out:
                print(_json.dumps({"error": "streaming_disabled"}, indent=2))
            else:
                print("Streaming payments are disabled on this provider.")
            raise typer.Exit(code=1)
        c = Container()
        c.config.from_pydantic(settings)
        stream_map = c.stream_map()
        reader = StreamPaymentReader(settings.POLYGON_RPC_URL, settings.STREAM_PAYMENT_ADDRESS)
        items = asyncio.run(stream_map.all_items())
        now = int(reader.web3.eth.get_block("latest")["timestamp"]) if items else 0
        rows = []
        for vm_id, stream_id in items.items():
            try:
                s = reader.get_stream(int(stream_id))
                vested = max(min(now, int(s["stopTime"])) - int(s["startTime"]), 0) * int(s["ratePerSecond"])  # type: ignore
                withdrawable = max(int(vested) - int(s["withdrawn"]), 0)
                remaining = max(int(s["stopTime"]) - now, 0)
                ok, reason = reader.verify_stream(int(stream_id), settings.PROVIDER_ID)
                rows.append({
                    "vm_id": vm_id,
                    "stream_id": int(stream_id),
                    "token": str(s.get("token")),
                    "recipient": s["recipient"],
                    "start": int(s["startTime"]),
                    "stop": int(s["stopTime"]),
                    "rate": int(s["ratePerSecond"]),
                    "deposit": int(s["deposit"]),
                    "withdrawn": int(s["withdrawn"]),
                    "remaining": remaining,
                    "verified": bool(ok),
                    "reason": reason,
                    "withdrawable": int(withdrawable),
                })
            except Exception as e:
                rows.append({"vm_id": vm_id, "stream_id": int(stream_id), "error": str(e)})
        if json_out:
            print(_json.dumps({"streams": rows}, indent=2))
            return
        if not rows:
            print("No streams mapped.")
            return
        # Prepare human-friendly display (ETH/GLM + USD)
        ZERO = "0x0000000000000000000000000000000000000000"
        # Cache prices so we don't query per-row
        price_cache: dict[str, Optional[Decimal]] = {"ETH": None, "GLM": None}
        # Determine which symbols are present
        symbols_present = set()
        for r in rows:
            if "error" in r:
                continue
            token_addr = (r.get("token") or "").lower()
            sym = "ETH" if token_addr == ZERO.lower() else "GLM"
            symbols_present.add(sym)
        if "ETH" in symbols_present:
            price_cache["ETH"] = fetch_eth_usd_price()
        if "GLM" in symbols_present:
            price_cache["GLM"] = fetch_glm_usd_price()

        # Build table rows
        table_rows = []
        for r in rows:
            if "error" in r:
                table_rows.append([r["vm_id"], str(r["stream_id"]), "—", "ERROR", r.get("error", ""), "—"])
                continue
            token_addr = (r.get("token") or "").lower()
            sym = "ETH" if token_addr == ZERO.lower() else "GLM"
            withdrawable_eth = Decimal(str(Web3.from_wei(int(r["withdrawable"]), "ether")))
            withdrawable_str = f"{withdrawable_eth:.6f} {sym}"
            price = price_cache.get(sym)
            usd_str = "—"
            if price is not None:
                try:
                    usd_val = (withdrawable_eth * price).quantize(Decimal("0.01"))
                    usd_str = f"${usd_val}"
                except Exception:
                    usd_str = "—"
            table_rows.append([
                r["vm_id"],
                str(r["stream_id"]),
                f"{int(r['remaining'])}s",
                "yes" if r["verified"] else "no",
                withdrawable_str,
                usd_str,
            ])

        headers = ["VM", "Stream", "Remaining", "Verified", "Withdrawable", "USD"]
        # Compute column widths
        cols = len(headers)
        col_widths = [len(h) for h in headers]
        for row in table_rows:
            for i in range(cols):
                col_widths[i] = max(col_widths[i], len(str(row[i])))

        def fmt_row(values: list[str]) -> str:
            return "  ".join(str(values[i]).ljust(col_widths[i]) for i in range(cols))

        print("\nStreams")
        print(fmt_row(headers))
        print("  ".join("-" * w for w in col_widths))
        for row in table_rows:
            print(fmt_row(row))
    except Exception as e:
        if json_out:
            print(_json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"Error: {e}")
        raise typer.Exit(code=1)
    finally:
        if json_out:
            try:
                del os.environ["GOLEM_SILENCE_LOGS"]
            except Exception:
                pass


@streams_app.command("show")
def streams_show(vm_id: str = typer.Argument(..., help="VM id (requestor_name)"), json_out: bool = typer.Option(False, "--json")):
    """Show a single VM's stream status."""
    from .container import Container
    from .config import settings
    from .payments.blockchain_service import StreamPaymentReader
    from .utils.pricing import fetch_glm_usd_price, fetch_eth_usd_price
    from decimal import Decimal
    from web3 import Web3
    import json as _json
    try:
        if json_out:
            os.environ["GOLEM_SILENCE_LOGS"] = "1"
        c = Container()
        c.config.from_pydantic(settings)
        stream_map = c.stream_map()
        sid = asyncio.run(stream_map.get(vm_id))
        if sid is None:
            if json_out:
                print(_json.dumps({"error": "no_stream_mapping", "vm_id": vm_id}, indent=2))
            else:
                print("No stream mapped for this VM.")
            raise typer.Exit(code=1)
        reader = StreamPaymentReader(settings.POLYGON_RPC_URL, settings.STREAM_PAYMENT_ADDRESS)
        s = reader.get_stream(int(sid))
        now = int(reader.web3.eth.get_block("latest")["timestamp"])  # type: ignore
        vested = max(min(now, int(s["stopTime"])) - int(s["startTime"]), 0) * int(s["ratePerSecond"])  # type: ignore
        withdrawable = max(int(vested) - int(s["withdrawn"]), 0)
        remaining = max(int(s["stopTime"]) - now, 0)
        ok, reason = reader.verify_stream(int(sid), settings.PROVIDER_ID)
        out = {
            "vm_id": vm_id,
            "stream_id": int(sid),
            "chain": s,
            "computed": {
                "now": now,
                "remaining_seconds": remaining,
                "vested_wei": int(vested),
                "withdrawable_wei": int(withdrawable),
            },
            "verified": bool(ok),
            "reason": reason,
        }
        if json_out:
            print(_json.dumps(out, indent=2))
        else:
            ZERO = "0x0000000000000000000000000000000000000000"
            token_addr = (s.get("token") or "").lower()
            sym = "ETH" if token_addr == ZERO.lower() else "GLM"
            nat = Decimal(str(Web3.from_wei(int(withdrawable), "ether")))
            price = fetch_eth_usd_price() if sym == "ETH" else fetch_glm_usd_price()
            usd_str = "—"
            if price is not None:
                try:
                    usd_val = (nat * price).quantize(Decimal("0.01"))
                    usd_str = f"${usd_val}"
                except Exception:
                    usd_str = "—"
            def _fmt_seconds(sec: int) -> str:
                m, s2 = divmod(int(sec), 60)
                h, m = divmod(m, 60)
                d, h = divmod(h, 24)
                parts = []
                if d: parts.append(f"{d}d")
                if h: parts.append(f"{h}h")
                if m and not d: parts.append(f"{m}m")
                if s2 and not d and not h and not m: parts.append(f"{s2}s")
                return " ".join(parts) or "0s"
            # Pretty single-record display
            print("\nStream Details")
            headers = ["VM", "Stream", "Remaining", "Verified", "Withdrawable", "USD"]
            cols = [
                vm_id,
                str(sid),
                _fmt_seconds(remaining),
                "yes" if ok else "no",
                f"{nat:.6f} {sym}",
                usd_str,
            ]
            w = [max(len(headers[i]), len(str(cols[i]))) for i in range(len(headers))]
            print("  ".join(headers[i].ljust(w[i]) for i in range(len(w))))
            print("  ".join("-" * wi for wi in w))
            print("  ".join(str(cols[i]).ljust(w[i]) for i in range(len(w))))
    except Exception as e:
        if json_out:
            print(_json.dumps({"error": str(e), "vm_id": vm_id}, indent=2))
        else:
            print(f"Error: {e}")
        raise typer.Exit(code=1)
    finally:
        if json_out:
            try:
                del os.environ["GOLEM_SILENCE_LOGS"]
            except Exception:
                pass

@streams_app.command("earnings")
def streams_earnings(json_out: bool = typer.Option(False, "--json", help="Output in JSON")):
    """Summarize provider earnings: vested, withdrawn, and withdrawable totals."""
    from .container import Container
    from .config import settings
    from .payments.blockchain_service import StreamPaymentReader
    from .utils.pricing import fetch_glm_usd_price, fetch_eth_usd_price
    from decimal import Decimal
    from web3 import Web3
    import json as _json
    try:
        if json_out:
            os.environ["GOLEM_SILENCE_LOGS"] = "1"
        c = Container()
        c.config.from_pydantic(settings)
        stream_map = c.stream_map()
        reader = StreamPaymentReader(settings.POLYGON_RPC_URL, settings.STREAM_PAYMENT_ADDRESS)
        items = asyncio.run(stream_map.all_items())
        now = int(reader.web3.eth.get_block("latest")["timestamp"]) if items else 0
        rows = []
        total_vested = 0
        total_withdrawn = 0
        total_withdrawable = 0
        ZERO = "0x0000000000000000000000000000000000000000"
        sums_native: dict[str, Decimal] = {"ETH": Decimal("0"), "GLM": Decimal("0")}
        for vm_id, stream_id in items.items():
            try:
                s = reader.get_stream(int(stream_id))
                vested = max(min(now, int(s["stopTime"])) - int(s["startTime"]), 0) * int(s["ratePerSecond"])  # type: ignore
                withdrawable = max(int(vested) - int(s["withdrawn"]), 0)
                total_vested += int(vested)
                total_withdrawn += int(s["withdrawn"])  # type: ignore
                total_withdrawable += int(withdrawable)
                sym = "ETH" if (s.get("token") or "").lower() == ZERO.lower() else "GLM"
                sums_native[sym] += Decimal(str(Web3.from_wei(int(withdrawable), "ether")))
                rows.append({
                    "vm_id": vm_id,
                    "stream_id": int(stream_id),
                    "token": str(s.get("token")),
                    "vested": int(vested),
                    "withdrawn": int(s["withdrawn"]),
                    "withdrawable": int(withdrawable),
                })
            except Exception as e:
                rows.append({"vm_id": vm_id, "stream_id": int(stream_id), "error": str(e)})
        out = {
            "streams": rows,
            "totals": {
                "vested": int(total_vested),
                "withdrawn": int(total_withdrawn),
                "withdrawable": int(total_withdrawable),
            }
        }
        if json_out:
            print(_json.dumps(out, indent=2))
            return
        # Human summary by token with USD
        price_eth = fetch_eth_usd_price()
        price_glm = fetch_glm_usd_price()
        def _fmt_usd(amount_native: Decimal, price: Optional[Decimal]) -> str:
            if price is None:
                return "—"
            try:
                return f"${(amount_native * price).quantize(Decimal('0.01'))}"
            except Exception:
                return "—"
        print("\nEarnings Summary")
        headers = ["Token", "Withdrawable", "USD"]
        data_rows = [
            ["ETH", f"{sums_native['ETH']:.6f} ETH", _fmt_usd(sums_native["ETH"], price_eth)],
            ["GLM", f"{sums_native['GLM']:.6f} GLM", _fmt_usd(sums_native["GLM"], price_glm)],
        ]
        # Table widths
        w = [len(h) for h in headers]
        for r in data_rows:
            for i in range(3):
                w[i] = max(w[i], len(str(r[i])))
        print("  ".join(headers[i].ljust(w[i]) for i in range(3)))
        print("  ".join("-" * wi for wi in w))
        for r in data_rows:
            print("  ".join(str(r[i]).ljust(w[i]) for i in range(3)))
        # Per stream table
        if rows:
            table = []
            for r in rows:
                if "error" in r:
                    table.append([r["vm_id"], str(r["stream_id"]), "ERROR", r.get("error", "")])
                    continue
                sym = "ETH" if (r.get("token") or "").lower() == ZERO.lower() else "GLM"
                nat = Decimal(str(Web3.from_wei(int(r["withdrawable"]), "ether")))
                price = price_eth if sym == "ETH" else price_glm
                usd = _fmt_usd(nat, price)
                table.append([r["vm_id"], str(r["stream_id"]), f"{nat:.6f} {sym}", usd])
            h2 = ["VM", "Stream", "Withdrawable", "USD"]
            w2 = [len(x) for x in h2]
            for row in table:
                for i in range(4):
                    w2[i] = max(w2[i], len(str(row[i])))
            print("\nPer Stream")
            print("  ".join(h2[i].ljust(w2[i]) for i in range(4)))
            print("  ".join("-" * wi for wi in w2))
            for row in table:
                print("  ".join(str(row[i]).ljust(w2[i]) for i in range(4)))
    except Exception as e:
        if json_out:
            try:
                print(_json.dumps({"error": str(e)}, indent=2))
            except Exception:
                print("{\"error\": \"unexpected\"}")
        else:
            print(f"Error: {e}")
        raise typer.Exit(code=1)
    finally:
        if json_out:
            try:
                del os.environ["GOLEM_SILENCE_LOGS"]
            except Exception:
                pass


@streams_app.command("withdraw")
def streams_withdraw(
    vm_id: str = typer.Option(None, "--vm-id", help="Withdraw for a single VM id"),
    all_streams: bool = typer.Option(False, "--all", help="Withdraw for all mapped streams"),
):
    """Withdraw vested funds for one or all streams."""
    from .container import Container
    from .config import settings
    from .security.l2_faucet import L2FaucetService
    try:
        if not vm_id and not all_streams:
            print("Specify --vm-id or --all")
            raise typer.Exit(code=1)
        c = Container()
        c.config.from_pydantic(settings)
        stream_map = c.stream_map()
        client = c.stream_client()
        # Ensure we have L2 gas for withdrawals (testnets)
        try:
            asyncio.run(L2FaucetService(settings).request_funds(settings.PROVIDER_ID))
        except Exception:
            # Non-fatal; proceed with withdraw attempt
            pass
        targets = []
        if all_streams:
            items = asyncio.run(stream_map.all_items())
            for vid, sid in items.items():
                targets.append((vid, int(sid)))
        else:
            sid = asyncio.run(stream_map.get(vm_id))
            if sid is None:
                print("No stream mapped for this VM.")
                raise typer.Exit(code=1)
            targets.append((vm_id, int(sid)))
        results = []
        for vid, sid in targets:
            try:
                tx = client.withdraw(int(sid))
                results.append((vid, sid, tx))
                print(f"Withdrew stream {sid} for VM {vid}: tx={tx}")
            except Exception as e:
                print(f"Failed to withdraw stream {sid} for VM {vid}: {e}")
        # no JSON aggregation here; use earnings for structured output
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(code=1)

@cli.command()
def start(
    no_verify_port: bool = typer.Option(False, "--no-verify-port", help="Skip provider port verification."),
    network: str = typer.Option(None, "--network", help="Target network: 'testnet' or 'mainnet' (overrides env)")
):
    """Start the provider server."""
    run_server(dev_mode=False, no_verify_port=no_verify_port, network=network)

# Removed separate 'dev' command; use environment GOLEM_PROVIDER_ENVIRONMENT=development instead.

def _env_path_for(dev_mode: Optional[bool]) -> str:
    from pathlib import Path
    env_file = ".env.dev" if dev_mode else ".env"
    return str(Path(__file__).parent.parent / env_file)

def _write_env_vars(path: str, updates: dict):
    # Simple .env updater: preserves other lines, replaces/append updated keys
    import re
    import io
    try:
        with open(path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    kv = {**updates}
    pattern = re.compile(r"^(?P<k>[A-Z0-9_]+)=.*$")
    out = []
    seen = set()
    for line in lines:
        m = pattern.match(line.strip())
        if not m:
            out.append(line)
            continue
        k = m.group("k")
        if k in kv:
            out.append(f"{k}={kv[k]}\n")
            seen.add(k)
        else:
            out.append(line)
    for k, v in kv.items():
        if k not in seen:
            out.append(f"{k}={v}\n")

    with open(path, "w") as f:
        f.writelines(out)


@config_app.command("withdraw")
def config_withdraw(
    enable: bool = typer.Option(None, "--enable", help="Enable/disable auto-withdraw (true/false)"),
    interval: int = typer.Option(None, "--interval", help="Withdraw interval in seconds (e.g., 1800)"),
    min_wei: int = typer.Option(None, "--min-wei", help="Only withdraw when >= this wei amount"),
    dev: bool = typer.Option(False, "--dev", help="Write to .env.dev instead of .env"),
):
    """Configure provider auto-withdraw settings and persist to .env(.dev)."""
    from .config import settings
    env_path = _env_path_for(dev)
    updates = {}
    if enable is not None:
        updates["GOLEM_PROVIDER_STREAM_WITHDRAW_ENABLED"] = str(enable).lower()
        settings.STREAM_WITHDRAW_ENABLED = bool(enable)
    if interval is not None:
        if interval < 0:
            raise typer.BadParameter("--interval must be >= 0")
        updates["GOLEM_PROVIDER_STREAM_WITHDRAW_INTERVAL_SECONDS"] = int(interval)
        try:
            settings.STREAM_WITHDRAW_INTERVAL_SECONDS = int(interval)
        except Exception:
            pass
    if min_wei is not None:
        if min_wei < 0:
            raise typer.BadParameter("--min-wei must be >= 0")
        updates["GOLEM_PROVIDER_STREAM_MIN_WITHDRAW_WEI"] = int(min_wei)
        try:
            settings.STREAM_MIN_WITHDRAW_WEI = int(min_wei)
        except Exception:
            pass
    if not updates:
        print("No changes (use --enable/--interval/--min-wei)")
        raise typer.Exit(code=0)
    _write_env_vars(env_path, updates)
    print(f"Updated withdraw settings in {env_path}")


@config_app.command("monitor")
def config_monitor(
    enable: bool = typer.Option(None, "--enable", help="Enable/disable stream monitor (true/false)"),
    interval: int = typer.Option(None, "--interval", help="Monitor interval in seconds (e.g., 30)"),
    min_remaining: int = typer.Option(None, "--min-remaining", help="Minimum remaining runway to keep VM running (seconds)"),
    dev: bool = typer.Option(False, "--dev", help="Write to .env.dev instead of .env"),
):
    """Configure provider stream monitor and persist to .env(.dev)."""
    from .config import settings
    env_path = _env_path_for(dev)
    updates = {}
    if enable is not None:
        updates["GOLEM_PROVIDER_STREAM_MONITOR_ENABLED"] = str(enable).lower()
        settings.STREAM_MONITOR_ENABLED = bool(enable)
    if interval is not None:
        if interval < 0:
            raise typer.BadParameter("--interval must be >= 0")
        updates["GOLEM_PROVIDER_STREAM_MONITOR_INTERVAL_SECONDS"] = int(interval)
        try:
            settings.STREAM_MONITOR_INTERVAL_SECONDS = int(interval)
        except Exception:
            pass
    if min_remaining is not None:
        if min_remaining < 0:
            raise typer.BadParameter("--min-remaining must be >= 0")
        updates["GOLEM_PROVIDER_STREAM_MIN_REMAINING_SECONDS"] = int(min_remaining)
        try:
            settings.STREAM_MIN_REMAINING_SECONDS = int(min_remaining)
        except Exception:
            pass
    if not updates:
        print("No changes (use --enable/--interval/--min-remaining)")
        raise typer.Exit(code=0)
    _write_env_vars(env_path, updates)
    print(f"Updated monitor settings in {env_path}")

def _print_pricing_examples(glm_usd):
    from decimal import Decimal
    from .utils.pricing import calculate_monthly_cost, calculate_monthly_cost_usd
    from .vm.models import VMResources
    examples = [
        ("Small", VMResources(cpu=1, memory=1, storage=10)),
        ("Medium", VMResources(cpu=2, memory=4, storage=20)),
        ("Example 2c/2g/10g", VMResources(cpu=2, memory=2, storage=10)),
    ]
    # Maintain legacy header for tests while adding a clearer caption
    print("\nExample monthly costs with current settings:")
    print("(Estimated monthly earnings with your current pricing)")
    for name, res in examples:
        glm = calculate_monthly_cost(res)
        usd = calculate_monthly_cost_usd(res, glm_usd)
        usd_str = f"${usd:.2f}" if usd is not None else "—"
        glm_str = f"{glm:.4f} GLM"
        print(
            f"- {name} ({res.cpu}C, {res.memory}GB RAM, {res.storage}GB Disk): ~{usd_str} per month (~{glm_str})"
        )

def run_server(dev_mode: bool | None = None, no_verify_port: bool = False, network: str | None = None):
    """Helper to run the uvicorn server."""
    import sys
    from pathlib import Path
    from dotenv import load_dotenv
    import uvicorn
    # Decide dev mode from explicit arg or environment
    if dev_mode is None:
        dev_mode = os.environ.get("GOLEM_PROVIDER_ENVIRONMENT", "").lower() == "development"

    # Load appropriate .env file based on mode
    env_file = ".env.dev" if dev_mode else ".env"
    env_path = Path(__file__).parent.parent / env_file
    load_dotenv(dotenv_path=env_path)

    # Apply network override early (affects settings and annotations)
    if network:
        os.environ["GOLEM_PROVIDER_NETWORK"] = network
    
    # The logic for setting the public IP in dev mode is now handled in config.py
    # The following lines are no longer needed and have been removed.

    # Import settings after loading env
    from .config import settings
    if network:
        try:
            settings.NETWORK = network
        except Exception:
            pass

    # Configure logging with debug mode
    logger = setup_logger(__name__, debug=dev_mode)

    try:
        # Log environment variables
        logger.info("Environment variables:")
        for key, value in os.environ.items():
            if key.startswith('GOLEM_PROVIDER_'):
                logger.info(f"{key}={value}")
        if network:
            logger.info(f"Overridden network: {network}")

        # Check requirements
        if not check_requirements():
            logger.error("Requirements check failed")
            sys.exit(1)

        # Verify provider port is available
        if not no_verify_port and not asyncio.run(verify_provider_port(settings.PORT)):
            logger.error(f"Provider port {settings.PORT} is not available")
            sys.exit(1)

        # Configure uvicorn logging
        log_config = uvicorn.config.LOGGING_CONFIG
        log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        # Run server
        logger.process(
            f"🚀 Starting provider server on {settings.HOST}:{settings.PORT}")
        uvicorn.run(
            "provider:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=dev_mode,
            log_level="debug" if dev_mode else "info",
            log_config=log_config,
            timeout_keep_alive=60,  # Increase keep-alive timeout
            limit_concurrency=100,  # Limit concurrent connections
        )
    except Exception as e:
        logger.error(f"Failed to start provider server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    cli()


@pricing_app.command("show")
def pricing_show():
    """Show current USD and GLM per-unit monthly prices and examples."""
    from decimal import Decimal
    from .utils.pricing import fetch_glm_usd_price, update_glm_unit_prices_from_usd

    print("Current pricing (per month):")
    print(
        f"  - USD per unit: CPU ${settings.PRICE_USD_PER_CORE_MONTH}/core, RAM ${settings.PRICE_USD_PER_GB_RAM_MONTH}/GB, Disk ${settings.PRICE_USD_PER_GB_STORAGE_MONTH}/GB"
    )
    glm_usd = fetch_glm_usd_price()
    if not glm_usd:
        print("Error: Could not fetch GLM/USD price. Please try again later.")
        raise typer.Exit(code=1)
    # Coerce to Decimal for calculations if needed
    from decimal import Decimal
    if not isinstance(glm_usd, Decimal):
        glm_usd = Decimal(str(glm_usd))
    update_glm_unit_prices_from_usd(glm_usd)
    print(f"  - GLM price: ${glm_usd} per GLM")
    print(f"  - Rate: {glm_usd} USD/GLM")
    print(
        f"  - GLM per unit: CPU {round(float(settings.PRICE_GLM_PER_CORE_MONTH), 6)} GLM/core, RAM {round(float(settings.PRICE_GLM_PER_GB_RAM_MONTH), 6)} GLM/GB, Disk {round(float(settings.PRICE_GLM_PER_GB_STORAGE_MONTH), 6)} GLM/GB"
    )
    _print_pricing_examples(glm_usd)


@pricing_app.command("set")
def pricing_set(
    usd_per_core: float = typer.Option(
        ..., "--usd-per-core", "--core-usd", help="USD per CPU core per month"
    ),
    usd_per_mem: float = typer.Option(
        ..., "--usd-per-mem", "--ram-usd", help="USD per GB of RAM per month"
    ),
    usd_per_disk: float = typer.Option(
        ..., "--usd-per-disk", "--usd-per-storage", "--storage-usd", help="USD per GB of disk per month"
    ),
    dev: bool = typer.Option(False, "--dev", help="Write to .env.dev instead of .env"),
):
    """Set USD pricing; GLM rates auto-update via CoinGecko in background."""
    if usd_per_core < 0 or usd_per_mem < 0 or usd_per_disk < 0:
        raise typer.BadParameter("All pricing values must be >= 0")
    env_path = _env_path_for(dev)
    updates = {
        "GOLEM_PROVIDER_PRICE_USD_PER_CORE_MONTH": usd_per_core,
        "GOLEM_PROVIDER_PRICE_USD_PER_GB_RAM_MONTH": usd_per_mem,
        "GOLEM_PROVIDER_PRICE_USD_PER_GB_STORAGE_MONTH": usd_per_disk,
    }
    _write_env_vars(env_path, updates)
    print(f"Updated pricing in {env_path}")
    # Immediately reflect in current process settings as well
    settings.PRICE_USD_PER_CORE_MONTH = usd_per_core
    settings.PRICE_USD_PER_GB_RAM_MONTH = usd_per_mem
    settings.PRICE_USD_PER_GB_STORAGE_MONTH = usd_per_disk

    from .utils.pricing import fetch_glm_usd_price, update_glm_unit_prices_from_usd
    glm_usd = fetch_glm_usd_price()
    if glm_usd:
        # Coerce to Decimal for calculations if needed
        from decimal import Decimal
        if not isinstance(glm_usd, Decimal):
            glm_usd = Decimal(str(glm_usd))
        update_glm_unit_prices_from_usd(glm_usd)
        print("Recalculated GLM prices due to updated USD configuration.")
        _print_pricing_examples(glm_usd)
    else:
        print("Warning: could not fetch GLM/USD; GLM unit prices not recalculated.")
        print("Tip: run 'golem-provider pricing show' when online to verify pricing with USD examples.")
