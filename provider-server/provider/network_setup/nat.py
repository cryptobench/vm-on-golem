import socket
from dataclasses import dataclass


@dataclass
class NatMappingResult:
    success: bool
    detail: str


class NatMapper:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    async def ensure_tcp_mapping(
        self,
        public_port: int,
        internal_port: int,
        description: str,
    ) -> NatMappingResult:
        if not self.enabled:
            return NatMappingResult(True, "automatic mapping disabled")
        try:
            import miniupnpc  # type: ignore
        except Exception:
            if public_port == internal_port and _has_public_interface():
                return NatMappingResult(True, "public interface")
            return NatMappingResult(
                False,
                "automatic router setup is unavailable on this system",
            )

        try:
            upnp = miniupnpc.UPnP()
            upnp.discoverdelay = 2000
            count = upnp.discover()
            if count < 1:
                return NatMappingResult(False, "No UPnP-compatible router was found.")
            upnp.selectigd()
            local_ip = upnp.lanaddr
            existing = upnp.getspecificportmapping(public_port, "TCP")
            if existing:
                if _mapping_targets_local_port(existing, local_ip, internal_port):
                    return NatMappingResult(True, f"HTTPS :{public_port}")
                return NatMappingResult(
                    False,
                    _mapping_conflict_detail(public_port, existing),
                )
            try:
                ok = upnp.addportmapping(
                    public_port,
                    "TCP",
                    local_ip,
                    internal_port,
                    description,
                    "",
                )
            except Exception as exc:
                if _is_mapping_conflict(exc):
                    existing = upnp.getspecificportmapping(public_port, "TCP")
                    if existing and _mapping_targets_local_port(
                        existing, local_ip, internal_port
                    ):
                        return NatMappingResult(True, f"HTTPS :{public_port}")
                    return NatMappingResult(
                        False,
                        _upnp_error_detail(exc),
                    )
                return NatMappingResult(
                    False,
                    _upnp_error_detail(exc),
                )
            if ok:
                return NatMappingResult(True, f"HTTPS :{public_port}")
            return NatMappingResult(
                False,
                "UPnP addportmapping returned false",
            )
        except Exception as exc:
            return NatMappingResult(False, _upnp_error_detail(exc))


def _mapping_targets_local_port(
    existing: tuple[object, ...], local_ip: str, internal_port: int
) -> bool:
    try:
        existing_host = str(existing[0])
        existing_port = int(existing[1])
    except (IndexError, TypeError, ValueError):
        return False
    return existing_host == local_ip and existing_port == int(internal_port)


def _mapping_conflict_detail(
    public_port: int, existing: tuple[object, ...] | None
) -> str:
    target = ""
    if existing:
        try:
            target = f" to {existing[0]}:{existing[1]}"
        except IndexError:
            target = ""
    return (
        f"Port {public_port} is already mapped by your router{target}. "
        "Remove the existing rule or choose a different public HTTPS/HTTP port."
    )


def _upnp_error_detail(exc: Exception) -> str:
    return str(exc) or type(exc).__name__


def _is_mapping_conflict(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return "ConflictInMappingEntry" in text or "conflict" in text.lower()


def _has_public_interface() -> bool:
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not (
                ip.startswith("10.")
                or ip.startswith("192.168.")
                or ip.startswith("172.16.")
                or ip.startswith("127.")
            ):
                return True
    except Exception:
        return False
    return False
