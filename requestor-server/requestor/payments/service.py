import logging

from requestor.config import RequestorConfig
from requestor.errors import ExternalServiceError
from requestor.provider_client.factory import ProviderClientFactory
from requestor.vm.repo import VMRepository

from .blockchain_service import StreamPaymentClient, StreamPaymentConfig
from .domain import CreateStreamCommand, StreamActionResult, VMStreamStatus

logger = logging.getLogger(__name__)


class RequestorPaymentService:
    """Coordinates requestor payment stream operations."""

    def __init__(
        self,
        settings: RequestorConfig,
        vm_repo: VMRepository,
        provider_client_factory: ProviderClientFactory,
    ):
        self.settings = settings
        self.vm_repo = vm_repo
        self.provider_client_factory = provider_client_factory

    def _client(self) -> StreamPaymentClient:
        return StreamPaymentClient(
            StreamPaymentConfig(
                rpc_url=self.settings.polygon_rpc_url,
                contract_address=self.settings.stream_payment_address,
                glm_token_address=self.settings.glm_token_address,
                private_key=self.settings.ethereum_private_key,
            )
        )

    async def create_stream(self, command: CreateStreamCommand) -> StreamActionResult:
        try:
            stream_id = self._client().create_stream(
                command.provider_address,
                command.deposit_wei,
                command.rate_per_second_wei,
            )
        except Exception as exc:
            logger.error("Requestor payment stream creation failed", exc_info=True)
            raise ExternalServiceError(
                f"failed to create payment stream: {exc}"
            ) from exc
        logger.info("Requestor payment stream created", extra={"stream_id": stream_id})
        return StreamActionResult(stream_id=stream_id, status="created")

    async def top_up_stream(
        self, stream_id: int, amount_wei: int
    ) -> StreamActionResult:
        try:
            tx_hash = self._client().top_up(stream_id, amount_wei)
        except Exception as exc:
            logger.error(
                "Requestor payment stream top-up failed",
                extra={"stream_id": stream_id},
                exc_info=True,
            )
            raise ExternalServiceError(
                f"failed to top up stream {stream_id}: {exc}"
            ) from exc
        logger.info(
            "Requestor payment stream top-up submitted",
            extra={"stream_id": stream_id, "transaction_hash": tx_hash},
        )
        return StreamActionResult(
            stream_id=stream_id,
            transaction_hash=tx_hash,
            status="submitted",
        )

    async def terminate_stream(self, stream_id: int) -> StreamActionResult:
        try:
            tx_hash = self._client().terminate(stream_id)
        except Exception as exc:
            logger.error(
                "Requestor payment stream termination failed",
                extra={"stream_id": stream_id},
                exc_info=True,
            )
            raise ExternalServiceError(
                f"failed to terminate stream {stream_id}: {exc}"
            ) from exc
        logger.info(
            "Requestor payment stream termination submitted",
            extra={"stream_id": stream_id, "transaction_hash": tx_hash},
        )
        return StreamActionResult(
            stream_id=stream_id,
            transaction_hash=tx_hash,
            status="submitted",
        )

    async def get_vm_stream_status(self, vm_name: str) -> VMStreamStatus:
        vm = self.vm_repo.require(vm_name)
        stream_id = vm.config.get("stream_id")
        if stream_id is None:
            endpoint_url = vm.config.get("provider_endpoint_url")
            if not endpoint_url:
                raise ExternalServiceError(
                    "provider endpoint unavailable for VM stream status"
                )
            async with self.provider_client_factory.for_provider_endpoint(
                str(endpoint_url)
            ) as client:
                status = await client.get_vm_stream_status(vm.vm_id)
                stream_id = status.get("stream_id")
        return VMStreamStatus(
            vm_name=vm.name,
            vm_id=vm.vm_id,
            stream_id=stream_id,
            provider_ip=vm.provider_ip,
            status=vm.status,
        )

    async def list_vm_stream_statuses(self) -> list[VMStreamStatus]:
        statuses = []
        for vm in self.vm_repo.list():
            statuses.append(await self.get_vm_stream_status(vm.name))
        return statuses
