import importlib
import logging

from port_checker.config import Settings
from port_checker.errors import (
    BadGatewayError,
    ConfigurationError,
    DependencyUnavailableError,
    NotFoundError,
)

_ARKIV_SDK_MODULE = "golem" + "_base_sdk"
logger = logging.getLogger(__name__)


def _patch_web3_provider_symbol() -> None:
    try:
        web3 = importlib.import_module("web3")
    except Exception:
        return
    if not hasattr(web3, "WebSocketProvider") and hasattr(web3, "WebsocketProvider"):
        setattr(web3, "WebSocketProvider", getattr(web3, "WebsocketProvider"))


async def _create_arkiv_client(rpc_url: str, ws_url: str):
    _patch_web3_provider_symbol()
    try:
        sdk = importlib.import_module(_ARKIV_SDK_MODULE)
    except Exception as exc:
        raise DependencyUnavailableError(
            "Arkiv support not installed on server"
        ) from exc

    kwargs = {"rpc_url": rpc_url, "ws_url": ws_url}
    ro_client = getattr(sdk, "GolemBaseROClient", None)
    sdk_client = getattr(sdk, "GolemBaseClient", None)
    if ro_client is not None:
        return await ro_client.create_ro_client(**kwargs)
    if sdk_client is not None and hasattr(sdk_client, "create_ro_client"):
        return await sdk_client.create_ro_client(**kwargs)
    if sdk_client is not None and hasattr(sdk_client, "create"):
        return await sdk_client.create(**kwargs)
    raise DependencyUnavailableError("No suitable Arkiv client constructor found")


def _entity_key_from_hex(value: str):
    types = importlib.import_module(f"{_ARKIV_SDK_MODULE}.types")
    entity_key = getattr(types, "EntityKey")
    generic_bytes = getattr(types, "GenericBytes")
    return entity_key(generic_bytes.from_hex_string(value))


class ArkivResolver:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def resolve_ip(
        self,
        provider_id: str,
        rpc_url: str | None = None,
        ws_url: str | None = None,
    ) -> str:
        rpc = (rpc_url or self.settings.arkiv_rpc_url).strip()
        ws = (ws_url or self.settings.arkiv_ws_url).strip()
        if not rpc or not ws:
            logger.error("Arkiv resolver missing RPC/WS configuration")
            raise ConfigurationError("Arkiv RPC/WS URLs not configured")

        client = None
        try:
            logger.debug(
                "Resolving provider through Arkiv",
                extra={"provider_id": provider_id},
            )
            client = await _create_arkiv_client(rpc, ws)
            entity = await self._find_entity(client, provider_id)
            metadata = await client.get_entity_metadata(
                _entity_key_from_hex(entity.entity_key)
            )
            annotations = {
                annotation.key: annotation.value
                for annotation in metadata.string_annotations
            }
            ip = self._pick_annotation(annotations, "golem_ip_address")
            if not ip:
                logger.warning(
                    "Provider advertisement missing Arkiv IP annotation",
                    extra={"provider_id": provider_id},
                )
                raise NotFoundError("Provider IP not found on Arkiv")
            logger.debug(
                "Resolved provider through Arkiv",
                extra={"provider_id": provider_id},
            )
            return ip
        except (ConfigurationError, DependencyUnavailableError) as exc:
            logger.error(
                "Arkiv resolver configuration/dependency failure",
                extra={"provider_id": provider_id, "error": str(exc)},
            )
            raise
        except NotFoundError:
            logger.warning(
                "Provider not found on Arkiv",
                extra={"provider_id": provider_id},
            )
            raise
        except Exception as exc:
            logger.error(
                "Arkiv resolver failed",
                extra={"provider_id": provider_id, "error": str(exc)},
            )
            raise BadGatewayError(f"Arkiv error: {exc}") from exc
        finally:
            if client is not None:
                await client.disconnect()

    async def _find_entity(self, client, provider_id: str):
        network = self.settings.expected_network
        queries = [f'golem_provider_id="{provider_id}" && golem_network="{network}"']
        if self.settings.is_development:
            queries.insert(
                0,
                f'dev_golem_provider_id="{provider_id}" && golem_network="{network}"',
            )
        for query in queries:
            logger.debug(
                "Querying Arkiv provider advertisements",
                extra={"provider_id": provider_id, "query": query},
            )
            results = await client.query_entities(query)
            if results:
                return results[0]
        raise NotFoundError("Provider not found on Arkiv")

    def _pick_annotation(self, annotations: dict[str, str], key: str) -> str | None:
        if self.settings.is_development:
            dev_value = annotations.get(f"dev_{key}")
            if dev_value and str(dev_value).strip():
                return str(dev_value).strip()
        value = annotations.get(key)
        return str(value).strip() if value is not None else None
