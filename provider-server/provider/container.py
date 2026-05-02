import os
from pathlib import Path

from dependency_injector import containers, providers

from .discovery.arkiv_publisher import ArkivDiscoveryPublisher
from .discovery.composite_publisher import CompositeDiscoveryPublisher
from .discovery.publishers import CentralDiscoveryPublisher
from .discovery.publishing_service import DiscoveryPublishingService
from .discovery.resource_tracker import ResourceTracker
from .jobs.store import JobStore
from .payments.blockchain_service import StreamPaymentClient
from .payments.blockchain_service import StreamPaymentConfig as _SPC
from .payments.blockchain_service import StreamPaymentReader
from .payments.monitor import StreamMonitor
from .payments.stream_map import StreamMap
from .payments.stream_status_service import StreamStatusService
from .provider_info.service import ProviderInfoService
from .service import ProviderService
from .summary.service import ProviderSummaryService
from .vm.application_service import VMApplicationService
from .vm.multipass_adapter import MultipassAdapter
from .vm.name_mapper import VMNameMapper
from .vm.port_manager import PortManager
from .vm.proxy_manager import PythonProxyManager
from .vm.service import VMService


class Container(containers.DeclarativeContainer):
    """Dependency injection container."""

    config = providers.Configuration()

    resource_tracker = providers.Singleton(ResourceTracker)

    discovery_publisher = providers.Selector(
        config.DISCOVERY_BACKEND,
        arkiv=providers.Singleton(
            ArkivDiscoveryPublisher,
            resource_tracker=resource_tracker,
        ),
        central=providers.Singleton(
            CentralDiscoveryPublisher,
            resource_tracker=resource_tracker,
        ),
        both=providers.Singleton(
            CompositeDiscoveryPublisher,
            resource_tracker=resource_tracker,
        ),
    )

    advertisement_service = providers.Singleton(
        DiscoveryPublishingService,
        publisher=discovery_publisher,
    )

    vm_name_mapper = providers.Singleton(
        VMNameMapper,
        db_path=providers.Callable(
            lambda base: Path(base) / "vm_names.json", config.VM_DATA_DIR
        ),
    )

    stream_map = providers.Singleton(
        StreamMap,
        storage_path=providers.Callable(
            lambda base: Path(base) / "streams.json", config.VM_DATA_DIR
        ),
    )

    port_manager = providers.Singleton(
        PortManager,
        start_port=config.PORT_RANGE_START,
        end_port=config.PORT_RANGE_END,
        state_file=providers.Callable(
            os.path.join, config.PROXY_STATE_DIR, "ports.json"
        ),
        discovery_port=config.PORT,
        skip_verification=config.SKIP_PORT_VERIFICATION,
    )

    proxy_manager = providers.Singleton(
        PythonProxyManager,
        port_manager=port_manager,
        name_mapper=vm_name_mapper,
    )

    vm_provider = providers.Singleton(
        MultipassAdapter,
        proxy_manager=proxy_manager,
        name_mapper=vm_name_mapper,
    )

    vm_service = providers.Singleton(
        VMService,
        provider=vm_provider,
        resource_tracker=resource_tracker,
        name_mapper=vm_name_mapper,
    )

    # Payments
    stream_reader = providers.Factory(
        StreamPaymentReader,
        rpc_url=config.POLYGON_RPC_URL,
        contract_address=config.STREAM_PAYMENT_ADDRESS,
    )

    stream_status_service = providers.Factory(
        StreamStatusService,
        settings=config,
        stream_map=stream_map,
        reader_factory=stream_reader.provider,
    )

    stream_client = providers.Factory(
        StreamPaymentClient,
        cfg=providers.Callable(
            lambda rpc, addr, pk: _SPC(
                rpc_url=rpc, contract_address=addr, private_key=pk
            ),
            config.POLYGON_RPC_URL,
            config.STREAM_PAYMENT_ADDRESS,
            config.ETHEREUM_PRIVATE_KEY,
        ),
    )

    stream_monitor = providers.Singleton(
        StreamMonitor,
        stream_map=stream_map,
        vm_service=vm_service,
        reader=stream_reader,
        client=stream_client,
        settings=config,
    )

    provider_service = providers.Singleton(
        ProviderService,
        vm_service=vm_service,
        advertisement_service=advertisement_service,
        port_manager=port_manager,
    )

    # Async job store for VM creations
    job_store = providers.Singleton(
        JobStore,
        db_path=providers.Callable(
            lambda base: Path(base) / "jobs.sqlite", config.VM_DATA_DIR
        ),
    )

    vm_application_service = providers.Factory(
        VMApplicationService,
        vm_service=vm_service,
        settings=config,
        stream_status_service=stream_status_service,
        job_store=job_store,
    )

    provider_info_service = providers.Factory(
        ProviderInfoService,
        settings=config,
    )

    summary_service = providers.Factory(
        ProviderSummaryService,
        settings=config,
        resource_tracker=resource_tracker,
        vm_service=vm_service,
    )
