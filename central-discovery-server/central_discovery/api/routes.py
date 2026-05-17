import logging
import secrets

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from central_discovery.auth import verify_provider_auth
from central_discovery.domain import (
    ProviderAuthenticateMessage,
    ProviderRemoveMessage,
    ProviderUpsertMessage,
    ProtocolError,
    RequestorSubscribeMessage,
    UnauthorizedError,
)
from central_discovery.registry import DiscoveryRegistry, send_event
from central_discovery.time import utc_now

router = APIRouter()
logger = logging.getLogger(__name__)
registry = DiscoveryRegistry()


@router.websocket("/discovery/providers")
async def provider_discovery_socket(websocket: WebSocket):
    await websocket.accept()
    nonce = secrets.token_urlsafe(24)
    provider_id = None
    await websocket.send_json(
        {
            "type": "hello",
            "protocol": "central-discovery.ws.v1",
            "nonce": nonce,
            "generated_at": utc_now().isoformat(),
        }
    )

    try:
        auth_message = ProviderAuthenticateMessage.parse_obj(
            await websocket.receive_json()
        )
        provider_id = verify_provider_auth(auth_message, nonce)
        await send_event(websocket, "authenticated", {"provider_id": provider_id})
        logger.info(
            "Provider discovery websocket authenticated",
            extra={"provider_id": provider_id},
        )

        while True:
            raw = await websocket.receive_json()
            message_type = raw.get("type") if isinstance(raw, dict) else None
            if message_type == "advertisement.upsert":
                message = ProviderUpsertMessage.parse_obj(raw)
                advertisement = await registry.upsert_provider(
                    provider_id, message.advertisement
                )
                await send_event(
                    websocket,
                    "advertisement.accepted",
                    {"advertisement": advertisement.dict()},
                )
            elif message_type == "advertisement.remove":
                ProviderRemoveMessage.parse_obj(raw)
                await registry.remove_provider(provider_id)
                await send_event(
                    websocket, "advertisement.removed", {"provider_id": provider_id}
                )
            else:
                raise ProtocolError(
                    f"unsupported provider message type: {message_type}"
                )
    except WebSocketDisconnect:
        logger.info(
            "Provider discovery websocket disconnected",
            extra={"provider_id": provider_id},
        )
    except UnauthorizedError as exc:
        await websocket.send_json({"type": "error", "error": str(exc)})
        await websocket.close(code=1008)
    except (ValidationError, ProtocolError) as exc:
        await websocket.send_json({"type": "error", "error": str(exc)})
        await websocket.close(code=1003)
    finally:
        if provider_id:
            await registry.remove_provider(provider_id)


@router.websocket("/discovery/requestors")
async def requestor_discovery_socket(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json(
        {
            "type": "hello",
            "protocol": "central-discovery.ws.v1",
            "generated_at": utc_now().isoformat(),
        }
    )

    try:
        while True:
            raw = await websocket.receive_json()
            message = RequestorSubscribeMessage.parse_obj(raw)
            advertisements = await registry.subscribe(websocket, message.filters)
            await send_event(
                websocket,
                "snapshot",
                {
                    "advertisements": [
                        advertisement.dict() for advertisement in advertisements
                    ]
                },
            )
    except WebSocketDisconnect:
        logger.debug("Requestor discovery websocket disconnected")
    except ValidationError as exc:
        await websocket.send_json({"type": "error", "error": str(exc)})
        await websocket.close(code=1003)
    finally:
        await registry.disconnect_requestor(websocket)
