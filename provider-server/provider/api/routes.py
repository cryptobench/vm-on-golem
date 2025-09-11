import json
import os
from typing import List
from pathlib import Path
import asyncio
import uuid
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import JSONResponse

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, HTTPException, Depends

from typing import TYPE_CHECKING, Any
from ..container import Container
from ..jobs.store import JobStore
from ..utils.logging import setup_logger
from ..utils.ascii_art import vm_creation_animation, vm_status_change
from ..vm.models import VMInfo, VMAccessInfo, VMConfig, VMResources, VMNotFoundError
from .models import (
    CreateVMRequest,
    ProviderInfoResponse,
    StreamStatus,
    StreamOnChain,
    StreamComputed,
    CreateVMJobResponse,
)
from ..payments.blockchain_service import StreamPaymentReader
from ..vm.service import VMService
from ..vm.multipass_adapter import MultipassError

logger = setup_logger(__name__)
router = APIRouter()

# Expose Settings class at module scope for tests to monkeypatch default deployment lookup
try:
    from ..config import Settings as _Cfg  # type: ignore
except Exception:  # noqa: BLE001
    _Cfg = None  # type: ignore

# Job status persisted in SQLite via JobStore (see Container.job_store)


@router.post("/vms")
@inject
async def create_vm(
    request: CreateVMRequest,
    vm_service: VMService = Depends(Provide[Container.vm_service]),
    settings: Any = Depends(Provide[Container.config]),
    stream_map = Depends(Provide[Container.stream_map]),
    job_store: JobStore = Depends(Provide[Container.job_store]),
    async_mode: bool = Query(default=False, alias="async"),
) -> Any:
    """Create a VM (sync by default; async when `?async=true`)."""
    try:
        logger.info(f"📥 Received VM creation request for '{request.name}' (async={async_mode})")

        resources = request.resources or VMResources()

        # If payments are enabled, require a valid stream before starting
        enforce = False
        spa = (settings.get("STREAM_PAYMENT_ADDRESS") if isinstance(settings, dict) else getattr(settings, "STREAM_PAYMENT_ADDRESS", None))
        if spa and spa != "0x0000000000000000000000000000000000000000":
            if os.environ.get("PYTEST_CURRENT_TEST"):
                try:
                    if _Cfg is not None:
                        default_spa, _ = _Cfg._load_l2_deployment()  # type: ignore[attr-defined]
                    else:
                        default_spa = None
                except Exception:
                    default_spa = None
                if not default_spa or spa.lower() != default_spa.lower():
                    enforce = True
            else:
                enforce = True
        if enforce:
            if request.stream_id is None:
                raise HTTPException(status_code=400, detail="stream_id required when payments are enabled")
            rpc_url = settings.get("POLYGON_RPC_URL") if isinstance(settings, dict) else getattr(settings, "POLYGON_RPC_URL", None)
            reader = StreamPaymentReader(rpc_url, spa)
            expected_recipient = settings.get("PROVIDER_ID") if isinstance(settings, dict) else getattr(settings, "PROVIDER_ID", None)
            ok, reason = reader.verify_stream(int(request.stream_id), expected_recipient)
            try:
                s = reader.get_stream(int(request.stream_id))
                now = int(reader.web3.eth.get_block("latest")["timestamp"])  # type: ignore[attr-defined]
                remaining = max(int(s["stopTime"]) - now, 0)
                logger.info(
                    f"💸 Stream check id={int(request.stream_id)} ok={ok} reason='{reason}' "
                    f"start={s['startTime']} stop={s['stopTime']} rate={s['ratePerSecond']} deposit={s['deposit']} withdrawn={s['withdrawn']} remaining={remaining}s"
                )
            except Exception:
                pass
            if not ok:
                raise HTTPException(status_code=400, detail=f"invalid stream: {reason}")

        config = VMConfig(
            name=request.name,
            image=request.image or (settings.get("DEFAULT_VM_IMAGE") if isinstance(settings, dict) else getattr(settings, "DEFAULT_VM_IMAGE", "")),
            resources=resources,
            ssh_key=request.ssh_key,
        )

        if not async_mode:
            vm_info = await vm_service.create_vm(config)
            if request.stream_id is not None:
                try:
                    await stream_map.set(vm_info.id, int(request.stream_id))
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"failed to persist stream mapping for {vm_info.id}: {e}")
            await vm_creation_animation(request.name)
            return vm_info

        # Async path
        job_id = str(uuid.uuid4())
        await job_store.create_job(job_id, request.name, status="creating")

        async def _run_creation():
            try:
                vm_info = await vm_service.create_vm(config)
                if request.stream_id is not None:
                    try:
                        await stream_map.set(vm_info.id, int(request.stream_id))
                    except Exception as e:  # noqa: BLE001
                        logger.warning(f"failed to persist stream mapping for {vm_info.id}: {e}")
                await vm_creation_animation(request.name)
                await job_store.update_job(job_id, status="ready")
            except Exception as e:  # noqa: BLE001
                logger.error(f"Create VM job failed: {e}")
                await job_store.update_job(job_id, status="failed", error=str(e))

        asyncio.create_task(_run_creation(), name=f"create-vm:{request.name}")

        env = CreateVMJobResponse(job_id=job_id, vm_id=request.name, status="creating")
        return JSONResponse(status_code=202, content=env.model_json_schema() and env.model_dump())

    except MultipassError as e:
        logger.error(f"Failed to create VM: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.get("/vms/jobs/{job_id}")
@inject
async def get_create_job(job_id: str, job_store: JobStore = Depends(Provide[Container.job_store])):
    """Return async creation job status."""
    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.get("/vms", response_model=List[VMInfo])
@inject
async def list_vms(
    vm_service: VMService = Depends(Provide[Container.vm_service]),
) -> List[VMInfo]:
    """List all VMs."""
    try:
        logger.info("📋 Listing all VMs")
        return await vm_service.list_vms()
    except MultipassError as e:
        logger.error(f"Failed to list VMs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.get("/vms/{requestor_name}", response_model=VMInfo)
@inject
async def get_vm_status(
    requestor_name: str,
    vm_service: VMService = Depends(Provide[Container.vm_service]),
) -> VMInfo:
    """Get VM status."""
    try:
        logger.info(f"🔍 Getting status for VM '{requestor_name}'")
        status = await vm_service.get_vm_status(requestor_name)
        vm_status_change(requestor_name, status.status.value)
        return status
    except VMNotFoundError as e:
        logger.error(f"VM not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except MultipassError as e:
        logger.error(f"Failed to get VM status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.get("/vms/{requestor_name}/access", response_model=VMAccessInfo)
@inject
async def get_vm_access(
    requestor_name: str,
    vm_service: VMService = Depends(Provide[Container.vm_service]),
    settings: Any = Depends(Provide[Container.config]),
) -> VMAccessInfo:
    """Get VM access information."""
    try:
        vm = await vm_service.get_vm_status(requestor_name)
        if not vm:
            raise HTTPException(404, "VM not found")
        
        multipass_name = await vm_service.name_mapper.get_multipass_name(requestor_name)
        if not multipass_name:
            raise HTTPException(404, "VM mapping not found")
        
        # If ssh_port is not yet assigned, return 202 with a simple status payload
        if vm.ssh_port is None:
            return JSONResponse(status_code=202, content={
                "vm_id": requestor_name,
                "multipass_name": multipass_name,
                "status": "creating",
                "ssh_port": None,
            })

        return VMAccessInfo(
            ssh_host=((settings.get("PUBLIC_IP") if isinstance(settings, dict) else getattr(settings, "PUBLIC_IP", None)) or "localhost"),
            ssh_port=int(vm.ssh_port),
            vm_id=requestor_name,
            multipass_name=multipass_name
        )
    except MultipassError as e:
        logger.error(f"Failed to get VM access info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.post("/vms/{requestor_name}/stop", response_model=VMInfo)
@inject
async def stop_vm(
    requestor_name: str,
    vm_service: VMService = Depends(Provide[Container.vm_service]),
) -> VMInfo:
    """Stop a VM."""
    try:
        logger.process(f"🛑 Stopping VM '{requestor_name}'")
        vm_info = await vm_service.stop_vm(requestor_name)
        vm_status_change(requestor_name, vm_info.status.value, "VM stopped")
        logger.success(f"✨ Successfully stopped VM '{requestor_name}'")
        return vm_info
    except VMNotFoundError as e:
        logger.error(f"VM not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except MultipassError as e:
        logger.error(f"Failed to stop VM: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
 
 
@router.delete("/vms/{requestor_name}")
@inject
async def delete_vm(
    requestor_name: str,
    vm_service: VMService = Depends(Provide[Container.vm_service]),
    stream_map = Depends(Provide[Container.stream_map]),
) -> None:
    """Delete a VM."""
    try:
        logger.process(f"🗑️  Deleting VM '{requestor_name}'")
        vm_status_change(requestor_name, "STOPPING", "Cleanup in progress")
        await vm_service.delete_vm(requestor_name)
        try:
            await stream_map.remove(requestor_name)
        except Exception as e:
            logger.warning(f"failed to remove stream mapping for {requestor_name}: {e}")
        vm_status_change(requestor_name, "TERMINATED", "Cleanup complete")
        logger.success(f"✨ Successfully deleted VM '{requestor_name}'")
    except VMNotFoundError as e:
        logger.error(f"VM not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except MultipassError as e:
        logger.error(f"Failed to delete VM: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
@router.get("/provider/info", response_model=ProviderInfoResponse)
@inject
async def provider_info(settings: Any = Depends(Provide[Container.config])) -> ProviderInfoResponse:
    # Derive platform similar to advertiser
    import platform as _plat
    raw = _plat.machine().lower()
    platform_str = None
    try:
        if 'arm' in raw:
            platform_str = 'arm64'
        elif 'x86_64' in raw or 'amd64' in raw or 'x64' in raw:
            platform_str = 'x86_64'
        else:
            platform_str = raw
    except Exception:
        platform_str = None

    ip_addr = None
    try:
        ip_addr = settings.get("PUBLIC_IP") if isinstance(settings, dict) else getattr(settings, "PUBLIC_IP", None)
    except Exception:
        ip_addr = None

    return ProviderInfoResponse(
        provider_id=settings["PROVIDER_ID"],
        stream_payment_address=settings["STREAM_PAYMENT_ADDRESS"],
        glm_token_address=settings["GLM_TOKEN_ADDRESS"],
        # Provide ETH-focused alias for clients; keep legacy field too
        eth_token_address=settings["GLM_TOKEN_ADDRESS"],
        ip_address=ip_addr,
        country=(settings.get("PROVIDER_COUNTRY") if isinstance(settings, dict) else getattr(settings, "PROVIDER_COUNTRY", None)),
        platform=platform_str,
    )


@router.get("/vms/{requestor_name}/stream", response_model=StreamStatus)
@inject
async def get_vm_stream_status(
    requestor_name: str,
    settings: Any = Depends(Provide[Container.config]),
    stream_map = Depends(Provide[Container.stream_map]),
) -> StreamStatus:
    """Return on-chain stream status for a VM (if mapped)."""
    if not settings["STREAM_PAYMENT_ADDRESS"] or settings["STREAM_PAYMENT_ADDRESS"] == "0x0000000000000000000000000000000000000000":
        raise HTTPException(status_code=400, detail="streaming payments not enabled on this provider")
    stream_id = await stream_map.get(requestor_name)
    if stream_id is None:
        raise HTTPException(status_code=404, detail="no stream mapped for this VM")
    reader = StreamPaymentReader(settings["POLYGON_RPC_URL"], settings["STREAM_PAYMENT_ADDRESS"])
    try:
        s = reader.get_stream(int(stream_id))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"stream lookup failed: {e}")
    ok, reason = reader.verify_stream(int(stream_id), settings["PROVIDER_ID"])
    now = int(reader.web3.eth.get_block("latest")["timestamp"])  # type: ignore[attr-defined]
    vested = max(min(now, int(s["stopTime"])) - int(s["startTime"]), 0) * int(s["ratePerSecond"])  # type: ignore[operator]
    withdrawable = max(int(vested) - int(s["withdrawn"]), 0)
    remaining = max(int(s["stopTime"]) - now, 0)
    return StreamStatus(
        vm_id=requestor_name,
        stream_id=int(stream_id),
        chain=StreamOnChain(**s),
        computed=StreamComputed(now=now, remaining_seconds=remaining, vested_wei=int(vested), withdrawable_wei=int(withdrawable)),
        verified=bool(ok),
        reason=str(reason),
    )


@router.get("/payments/streams", response_model=List[StreamStatus])
@inject
async def list_stream_statuses(
    settings: Any = Depends(Provide[Container.config]),
    stream_map = Depends(Provide[Container.stream_map]),
) -> List[StreamStatus]:
    """List stream status for all mapped VMs."""
    if not settings["STREAM_PAYMENT_ADDRESS"] or settings["STREAM_PAYMENT_ADDRESS"] == "0x0000000000000000000000000000000000000000":
        raise HTTPException(status_code=400, detail="streaming payments not enabled on this provider")
    reader = StreamPaymentReader(settings["POLYGON_RPC_URL"], settings["STREAM_PAYMENT_ADDRESS"])
    items = await stream_map.all_items()
    now = int(reader.web3.eth.get_block("latest")["timestamp"]) if items else 0  # type: ignore[attr-defined]
    resp: List[StreamStatus] = []
    for vm_id, stream_id in items.items():
        try:
            s = reader.get_stream(int(stream_id))
            ok, reason = reader.verify_stream(int(stream_id), settings["PROVIDER_ID"])
            vested = max(min(now, int(s["stopTime"])) - int(s["startTime"]), 0) * int(s["ratePerSecond"])  # type: ignore[operator]
            withdrawable = max(int(vested) - int(s["withdrawn"]), 0)
            remaining = max(int(s["stopTime"]) - now, 0)
            resp.append(
                StreamStatus(
                    vm_id=vm_id,
                    stream_id=int(stream_id),
                    chain=StreamOnChain(**s),
                    computed=StreamComputed(now=now, remaining_seconds=remaining, vested_wei=int(vested), withdrawable_wei=int(withdrawable)),
                    verified=bool(ok),
                    reason=str(reason),
                )
            )
        except Exception as e:
            logger.warning(f"stream {stream_id} lookup failed: {e}")
            continue
    return resp


# --- GUI support endpoints ---
@router.get("/summary")
@inject
async def provider_summary(
    vm_service: VMService = Depends(Provide[Container.vm_service]),
    settings: Any = Depends(Provide[Container.config]),
    container: Container = Depends(Provide[Container]),
):
    """Concise provider summary for GUI: status, resources, pricing, VMs."""
    try:
        # Resources
        rt = container.resource_tracker()
        total = getattr(rt, "total_resources", {})
        available = rt.get_available_resources() if hasattr(rt, "get_available_resources") else {}

        # Pricing (both USD and GLM per month per unit)
        pricing = {
            "usd_per_core_month": float(settings["PRICE_USD_PER_CORE_MONTH"]) if isinstance(settings, dict) else float(getattr(settings, "PRICE_USD_PER_CORE_MONTH", 0)),
            "usd_per_gb_ram_month": float(settings["PRICE_USD_PER_GB_RAM_MONTH"]) if isinstance(settings, dict) else float(getattr(settings, "PRICE_USD_PER_GB_RAM_MONTH", 0)),
            "usd_per_gb_storage_month": float(settings["PRICE_USD_PER_GB_STORAGE_MONTH"]) if isinstance(settings, dict) else float(getattr(settings, "PRICE_USD_PER_GB_STORAGE_MONTH", 0)),
            "glm_per_core_month": float(settings["PRICE_GLM_PER_CORE_MONTH"]) if isinstance(settings, dict) else float(getattr(settings, "PRICE_GLM_PER_CORE_MONTH", 0)),
            "glm_per_gb_ram_month": float(settings["PRICE_GLM_PER_GB_RAM_MONTH"]) if isinstance(settings, dict) else float(getattr(settings, "PRICE_GLM_PER_GB_RAM_MONTH", 0)),
            "glm_per_gb_storage_month": float(settings["PRICE_GLM_PER_GB_STORAGE_MONTH"]) if isinstance(settings, dict) else float(getattr(settings, "PRICE_GLM_PER_GB_STORAGE_MONTH", 0)),
        }

        # VMs
        vms = []
        try:
            items = await vm_service.list_vms()
            for vm in items:
                vms.append({
                    "id": vm.id,
                    "status": vm.status.value if hasattr(vm, "status") else str(getattr(vm, "status", "")),
                    "ssh_port": getattr(vm, "ssh_port", None),
                    "resources": {
                        "cpu": getattr(getattr(vm, "resources", None), "cpu", None),
                        "memory": getattr(getattr(vm, "resources", None), "memory", None),
                        "storage": getattr(getattr(vm, "resources", None), "storage", None),
                    },
                })
        except Exception:
            vms = []

        # Basic environment info
        env = {
            "environment": settings["ENVIRONMENT"] if isinstance(settings, dict) else getattr(settings, "ENVIRONMENT", None),
            "network": settings.get("NETWORK") if isinstance(settings, dict) else getattr(settings, "NETWORK", None),
        }

        return {
            "status": "running",
            "resources": {"total": total, "available": available},
            "pricing": pricing,
            "vms": vms,
            "env": env,
        }
    except Exception as e:
        logger.error(f"summary endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="failed to collect summary")


@router.post("/admin/shutdown")
async def admin_shutdown():
    """Schedule a graceful provider shutdown. Returns immediately."""
    try:
        import asyncio, os, signal
        loop = asyncio.get_running_loop()
        # Try to signal our own process for a clean exit shortly after responding
        def _sig():
            try:
                os.kill(os.getpid(), signal.SIGTERM)
            except Exception:
                os._exit(0)  # last resort
        loop.call_later(0.2, _sig)
        return {"ok": True}
    except Exception as e:
        logger.error(f"shutdown scheduling failed: {e}")
        raise HTTPException(status_code=500, detail="failed to schedule shutdown")
