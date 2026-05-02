"""Provider discovery and management service."""
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import aiohttp
from golem_base_sdk import GolemBaseClient
from golem_base_sdk.types import EntityKey, GenericBytes

from ..config import config
from ..discovery import (
    ArkivDiscoveryClient,
    CentralDiscoveryClient,
    ProviderSearchQuery,
    normalize_discovery_backend,
)
from ..errors import DiscoveryError, ProviderError


class ProviderService:
    """Service for provider operations."""

    def __init__(self):
        self.session = None
        self.golem_base_client = None
        self.arkiv_discovery = None
        self.central_discovery = None
        # Optional spec (cpu, memory, storage) to compute estimates for display
        self.estimate_spec: Optional[tuple[int, int, int]] = None

    def compute_estimate(
        self, provider: Dict, spec: tuple[int, int, int]
    ) -> Optional[Dict]:
        """Compute estimated pricing for a given spec, if provider has pricing.

        Returns dict with usd_per_month, glm_per_month (if GLM per-unit available),
        and usd_per_hour, or None if insufficient pricing data.
        """
        pricing = provider.get("pricing") or {}
        usd_core = pricing.get("usd_per_core_month")
        usd_ram = pricing.get("usd_per_gb_ram_month")
        usd_storage = pricing.get("usd_per_gb_storage_month")
        if usd_core is None or usd_ram is None or usd_storage is None:
            return None
        cpu, mem, sto = spec
        try:
            usd_per_month = (
                float(usd_core) * cpu + float(usd_ram) * mem + float(usd_storage) * sto
            )
            glm_core = pricing.get("glm_per_core_month")
            glm_ram = pricing.get("glm_per_gb_ram_month")
            glm_storage = pricing.get("glm_per_gb_storage_month")
            glm_per_month = None
            if glm_core is not None and glm_ram is not None and glm_storage is not None:
                glm_per_month = (
                    float(glm_core) * cpu
                    + float(glm_ram) * mem
                    + float(glm_storage) * sto
                )
            usd_per_hour = usd_per_month / 730.0
            # Round for display consistency
            return {
                "usd_per_month": round(usd_per_month, 4),
                "usd_per_hour": round(usd_per_hour, 6),
                "glm_per_month": round(glm_per_month, 8)
                if glm_per_month is not None
                else None,
            }
        except Exception:
            return None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        # The GolemBaseClient is now initialized on-demand in find_providers
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        if self.arkiv_discovery:
            await self.arkiv_discovery.close()

    async def find_providers(
        self,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        storage: Optional[int] = None,
        country: Optional[str] = None,
        platform: Optional[str] = None,
        driver: Optional[str] = None,
        payments_network: Optional[str] = None,
        include_all_payments: bool = False,
    ) -> List[Dict]:
        """Find providers matching requirements."""
        backend = normalize_discovery_backend(
            driver
            or getattr(config, "discovery_backend", None)
            or config.discovery_driver
        )
        query = ProviderSearchQuery(
            cpu=cpu,
            memory=memory,
            storage=storage,
            country=country,
            platform=platform,
            payments_network=payments_network,
            include_all_payments=include_all_payments,
        )
        if backend == "arkiv":
            from ..discovery import backends as discovery_backends

            discovery_backends.EntityKey = EntityKey
            discovery_backends.GenericBytes = GenericBytes
            if self.arkiv_discovery is None:
                self.arkiv_discovery = ArkivDiscoveryClient(GolemBaseClient)
            providers = await self.arkiv_discovery.find_providers(query)
            self.golem_base_client = self.arkiv_discovery.client
            return providers

        if self.session is None:
            self.session = aiohttp.ClientSession()
        if self.central_discovery is None:
            self.central_discovery = CentralDiscoveryClient(self.session)
        return await self.central_discovery.find_providers(query)

    async def _find_providers_golem_base(
        self,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        storage: Optional[int] = None,
        country: Optional[str] = None,
        platform: Optional[str] = None,
        payments_network: Optional[str] = None,
        include_all_payments: bool = False,
    ) -> List[Dict]:
        """Compatibility wrapper for the old Golem Base discovery method."""
        return await self.find_providers(
            cpu,
            memory,
            storage,
            country,
            platform,
            driver="arkiv",
            payments_network=payments_network,
            include_all_payments=include_all_payments,
        )

    async def _find_providers_central(
        self,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        storage: Optional[int] = None,
        country: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> List[Dict]:
        """Compatibility wrapper for the old central discovery method."""
        return await self.find_providers(
            cpu,
            memory,
            storage,
            country,
            platform,
            driver="central",
        )

    async def verify_provider(self, provider_id: str) -> Dict:
        """Verify provider exists and is available."""
        try:
            providers = await self.find_providers()
            provider = next(
                (p for p in providers if p["provider_id"] == provider_id), None
            )

            if not provider:
                raise ProviderError(f"Provider {provider_id} not found")

            return provider

        except Exception as e:
            if isinstance(e, ProviderError):
                raise
            raise ProviderError(f"Failed to verify provider: {str(e)}")

    async def get_provider_resources(self, provider_id: str) -> Dict:
        """Get current resource availability for a provider."""
        try:
            provider = await self.verify_provider(provider_id)
            return {
                "cpu": provider["resources"]["cpu"],
                "memory": provider["resources"]["memory"],
                "storage": provider["resources"]["storage"],
            }
        except Exception as e:
            raise ProviderError(f"Failed to get provider resources: {str(e)}")

    async def check_resource_availability(
        self, provider_id: str, cpu: int, memory: int, storage: int
    ) -> bool:
        """Check if provider has sufficient resources."""
        try:
            resources = await self.get_provider_resources(provider_id)

            return (
                resources["cpu"] >= cpu
                and resources["memory"] >= memory
                and resources["storage"] >= storage
            )

        except Exception as e:
            raise ProviderError(f"Failed to check resource availability: {str(e)}")

    async def _format_block_timestamp(self, block_number: int) -> str:
        """Format a block number into a human-readable 'time ago' string.

        The Golem Base chain uses ~2 seconds per block.
        We also guard against negative diffs that can occur when adverts are
        extended before expiry (expires_at increases), which would otherwise
        make the derived "created_at" appear in the future.
        """
        if not self.golem_base_client:
            return "N/A"
        try:
            latest_block = await self.golem_base_client.http_client().eth.get_block(
                "latest"
            )
            block_diff = latest_block.number - block_number
            if block_diff < 0:
                block_diff = 0
            # Approximate time: ~2s per block
            seconds_ago = block_diff * 2

            if seconds_ago < 60:
                return f"{int(seconds_ago)}s ago"
            elif seconds_ago < 3600:
                return f"{int(seconds_ago / 60)}m ago"
            elif seconds_ago < 86400:
                return f"{int(seconds_ago / 3600)}h ago"
            else:
                return f"{int(seconds_ago / 86400)}d ago"
        except Exception:
            return "N/A"

    async def format_provider_row(self, provider: Dict, colorize: bool = False) -> List:
        """Format provider information for display.

        Behavior:
        - When no full spec is provided (no ``estimate_spec``), show hourly per-unit
          prices (USD/core/hr, USD/GB RAM/hr, USD/GB Disk/hr) and omit monthly
          estimate columns to avoid confusing empty fields.
        - When a full spec is provided, show monthly per-unit prices and include
          estimated monthly totals (USD and GLM when available).
        """
        from click import style

        updated_at_str = await self._format_block_timestamp(
            provider.get("created_at_block", 0)
        )

        pricing = provider.get("pricing") or {}
        usd_core_mo = pricing.get("usd_per_core_month")
        usd_ram_mo = pricing.get("usd_per_gb_ram_month")
        usd_storage_mo = pricing.get("usd_per_gb_storage_month")

        # Precompute estimates if a spec is set and pricing available
        est_usd = "—"
        est_glm = "—"
        est_hr_usd = "—"
        if self.estimate_spec and all(
            p is not None for p in (usd_core_mo, usd_ram_mo, usd_storage_mo)
        ):
            spec_cpu, spec_mem, spec_sto = self.estimate_spec
            try:
                est_usd_val = (
                    (float(usd_core_mo) * spec_cpu)
                    + (float(usd_ram_mo) * spec_mem)
                    + (float(usd_storage_mo) * spec_sto)
                )
                est_usd = round(est_usd_val, 4)
                est_hr_usd = round(est_usd_val / 730.0, 6)
                # If GLM per-unit is present, compute GLM estimate as well
                glm_core = pricing.get("glm_per_core_month")
                glm_ram = pricing.get("glm_per_gb_ram_month")
                glm_storage = pricing.get("glm_per_gb_storage_month")
                if all(x is not None for x in (glm_core, glm_ram, glm_storage)):
                    est_glm_val = (
                        (float(glm_core) * spec_cpu)
                        + (float(glm_ram) * spec_mem)
                        + (float(glm_storage) * spec_sto)
                    )
                    est_glm = round(est_glm_val, 8)
            except Exception:
                pass

        # Show monthly unit prices when pricing exists; include estimate columns only
        # when a full spec was provided.
        show_monthly = bool(self.estimate_spec) or any(
            p is not None for p in (usd_core_mo, usd_ram_mo, usd_storage_mo)
        )
        show_estimates = bool(self.estimate_spec)

        if show_monthly:
            col_core = usd_core_mo if usd_core_mo is not None else "—"
            col_ram = usd_ram_mo if usd_ram_mo is not None else "—"
            col_sto = usd_storage_mo if usd_storage_mo is not None else "—"
        else:
            # Convert monthly unit prices to hourly for display when no spec provided
            def _per_hr(val):
                try:
                    return round(float(val) / 730.0, 6)
                except Exception:
                    return "—"

            col_core = _per_hr(usd_core_mo)
            col_ram = _per_hr(usd_ram_mo)
            col_sto = _per_hr(usd_storage_mo)

        row = [
            provider["provider_id"],
            provider["provider_name"],
            provider["ip_address"] or "N/A",
            provider["country"],
            provider["resources"]["cpu"],
            provider["resources"]["memory"],
            provider["resources"]["storage"],
            col_core,
            col_ram,
            col_sto,
        ]
        if show_estimates:
            row.extend([est_usd, est_glm])
        row.extend([(provider.get("platform") or "—"), updated_at_str])

        if colorize:
            # Format Provider ID
            id_txt = style(row[0], fg="yellow")
            if est_hr_usd != "—":
                id_txt += style(f"  (~${est_hr_usd}/hr)", fg="yellow")
            row[0] = id_txt

            # Format resources with icons and colors
            row[4] = style(f"💻 {row[4]}", fg="cyan", bold=True)
            row[5] = style(f"🧠 {row[5]}", fg="cyan", bold=True)
            row[6] = style(f"💾 {row[6]}", fg="cyan", bold=True)

            # Format pricing with currency markers
            # Determine base index for pricing columns
            # Indexes: 0=id,1=name,2=ip,3=country,4=cpu,5=mem,6=sto,7.. pricing
            price_idx = 7
            if show_estimates:
                # Monthly unit prices formatting
                if row[price_idx] != "—":
                    row[price_idx] = style(f"${row[price_idx]}/mo", fg="magenta")
                if row[price_idx + 1] != "—":
                    row[price_idx + 1] = style(
                        f"${row[price_idx + 1]}/GB/mo", fg="magenta"
                    )
                if row[price_idx + 2] != "—":
                    row[price_idx + 2] = style(
                        f"${row[price_idx + 2]}/GB/mo", fg="magenta"
                    )
                # Estimates
                if est_usd != "—":
                    row[price_idx + 3] = style(
                        f"~${row[price_idx + 3]}/mo", fg="yellow", bold=True
                    )
                if est_glm != "—":
                    row[price_idx + 4] = style(
                        f"~{row[price_idx + 4]} GLM/mo", fg="yellow"
                    )
                platform_idx = price_idx + 5
            else:
                unit_suffix = "mo" if show_monthly else "hr"
                if row[price_idx] != "—":
                    row[price_idx] = style(
                        f"${row[price_idx]}/{unit_suffix}", fg="magenta"
                    )
                if row[price_idx + 1] != "—":
                    row[price_idx + 1] = style(
                        f"${row[price_idx + 1]}/GB/{unit_suffix}", fg="magenta"
                    )
                if row[price_idx + 2] != "—":
                    row[price_idx + 2] = style(
                        f"${row[price_idx + 2]}/GB/{unit_suffix}", fg="magenta"
                    )
                platform_idx = price_idx + 3

            # Format location info
            row[3] = style(f"🌍 {row[3]}", fg="green", bold=True)

            # Platform column: dim label
            if row[platform_idx] != "—":
                row[platform_idx] = style(f"{row[platform_idx]}", fg="white")

        return row

    @property
    def provider_headers(self) -> List[str]:
        """Get headers for provider display.

        Estimate columns are included only when a full spec is provided.
        """
        base = [
            "Provider ID",
            "Name",
            "IP Address",
            "Country",
            "CPU",
            "Memory (GB)",
            "Disk (GB)",
        ]
        if self.estimate_spec:
            pricing_cols = [
                "USD/core/mo",
                "USD/GB RAM/mo",
                "USD/GB Disk/mo",
                "Est. $/mo",
                "Est. GLM/mo",
            ]
        else:
            pricing_cols = [
                "USD/core/mo",
                "USD/GB RAM/mo",
                "USD/GB Disk/mo",
            ]
        tail = [
            "Platform",
            "Updated",
        ]
        return base + pricing_cols + tail
