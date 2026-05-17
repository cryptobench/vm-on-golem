import os
from pathlib import Path

from dependency_injector import containers, providers

from .auth.services import ProviderAuthService
from .config import settings as provider_settings
from .discovery.arkiv_publisher import ArkivDiscoveryPublisher
from .discovery.composite_publisher import CompositeDiscoveryPublisher
from .discovery.publishers import CentralDiscoveryPublisher
from .discovery.publishing_service import DiscoveryPublishingService
from .discovery.resource_tracker import ResourceTracker
from .jobs.store import JobStore
from .live.events import ProviderEventBroadcaster
from .live.service import HostLiveService, ProviderLiveService, VMLiveService
from .monitoring.repo import MonitoringRepository
from .monitoring.services import MonitoringService
from .network_setup.certificate_service import CertificateMaintenanceService
from .network_setup.service import NetworkSetupService
from .payments.blockchain_service import StreamPaymentClient
from .payments.blockchain_service import StreamPaymentConfig as _SPC
from .payments.blockchain_service import StreamPaymentReader
from .payments.events import StreamPaymentEventService
from .payments.lease_quote_service import LeaseQuoteService
from .payments.monitor import StreamMonitor
from .payments.stream_map import StreamMap
from .payments.stream_status_service import StreamStatusService
from .provider_info.service import ProviderInfoService
from .service import ProviderService
from .settings.service import ProviderSettingsService
from .summary.service import ProviderSummaryService
from .vm.application_service import VMApplicationService
from .vm.multipass_adapter import MultipassAdapter
from .vm.name_mapper import VMNameMapper
from .vm.port_manager import PortManager
from .vm.proxy_manager import PythonProxyManager
from .vm.service import VMService
from .webhooks.repo import WebhookRepository
from .webhooks.service import WebhookService


class Container(containers.DeclarativeContainer):
    """Dependency injection container."""

    config = providers.Configuration()

    resource_tracker = providers.Singleton(ResourceTracker)

    provider_event_broadcaster = providers.Singleton(ProviderEventBroadcaster)

    certificate_maintenance_service = providers.Singleton(
        CertificateMaintenanceService,
        settings=provider_settings,
    )

    discovery_publisher = providers.Selector(
        config.DISCOVERY_BACKEND,
        arkiv=providers.Singleton(
            ArkivDiscoveryPublisher,
            resource_tracker=resource_tracker,
            certificate_service=certificate_maintenance_service,
        ),
        central=providers.Singleton(
            CentralDiscoveryPublisher,
            resource_tracker=resource_tracker,
            certificate_service=certificate_maintenance_service,
        ),
        both=providers.Singleton(
            CompositeDiscoveryPublisher,
            resource_tracker=resource_tracker,
            certificate_service=certificate_maintenance_service,
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
        state_file=providers.Callable(
            os.path.join, config.PROXY_STATE_DIR, "proxy_state.json"
        ),
    )

    monitoring_repo = providers.Singleton(
        MonitoringRepository,
        db_path=providers.Callable(
            lambda base: str(Path(base) / "monitoring.sqlite"), config.VM_DATA_DIR
        ),
    )

    webhook_repo = providers.Singleton(
        WebhookRepository,
        db_path=providers.Callable(
            lambda base: str(Path(base) / "monitoring.sqlite"), config.VM_DATA_DIR
        ),
    )

    webhook_service = providers.Singleton(
        WebhookService,
        settings=config,
        repo=webhook_repo,
        event_broadcaster=provider_event_broadcaster,
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
        monitoring_repo=monitoring_repo,
    )

    monitoring_service = providers.Singleton(
        MonitoringService,
        settings=config,
        repo=monitoring_repo,
        vm_service=vm_service,
        proxy_manager=proxy_manager,
        webhook_service=webhook_service,
    )

    # Payments
    stream_reader = providers.Factory(
        StreamPaymentReader,
        rpc_url=config.PAYMENTS_RPC_URL,
        contract_address=config.STREAM_PAYMENT_ADDRESS,
    )

    stream_status_service = providers.Factory(
        StreamStatusService,
        settings=config,
        stream_map=stream_map,
        reader_factory=stream_reader.provider,
    )

    lease_quote_service = providers.Factory(
        LeaseQuoteService,
        settings=config,
    )

    stream_client = providers.Factory(
        StreamPaymentClient,
        cfg=providers.Callable(
            lambda rpc, addr, pk: _SPC(
                rpc_url=rpc, contract_address=addr, private_key=pk
            ),
            config.PAYMENTS_RPC_URL,
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
        webhook_service=webhook_service,
    )

    stream_payment_event_service = providers.Singleton(
        StreamPaymentEventService,
        settings=config,
        stream_map=stream_map,
        reader_factory=stream_reader.provider,
        broadcaster=provider_event_broadcaster,
    )

    network_setup_service = providers.Singleton(
        NetworkSetupService,
        settings=provider_settings,
        certificate_service=certificate_maintenance_service,
    )

    provider_service = providers.Singleton(
        ProviderService,
        vm_service=vm_service,
        advertisement_service=advertisement_service,
        port_manager=port_manager,
        monitoring_service=monitoring_service,
        network_setup_service=network_setup_service,
        stream_payment_event_service=stream_payment_event_service,
    )

    # Async job store for VM creations
    job_store = providers.Singleton(
        JobStore,
        db_path=providers.Callable(
            lambda base: Path(base) / "jobs.sqlite", config.VM_DATA_DIR
        ),
    )

    provider_auth_service = providers.Singleton(
        ProviderAuthService,
        settings=config,
        stream_map=stream_map,
        job_store=job_store,
        reader_factory=stream_reader.provider,
    )

    vm_application_service = providers.Factory(
        VMApplicationService,
        vm_service=vm_service,
        settings=config,
        stream_status_service=stream_status_service,
        job_store=job_store,
        event_broadcaster=provider_event_broadcaster,
        webhook_service=webhook_service,
        stream_client=stream_client.provider,
    )

    provider_info_service = providers.Factory(
        ProviderInfoService,
        settings=config,
    )

    vm_live_service = providers.Singleton(
        VMLiveService,
        broadcaster=provider_event_broadcaster,
        monitoring_service=monitoring_service,
        vm_application_service=vm_application_service,
        provider_info_service=provider_info_service,
        stream_status_service=stream_status_service,
        auth_service=provider_auth_service,
    )

    host_live_service = providers.Singleton(
        HostLiveService,
        monitoring_service=monitoring_service,
        auth_service=provider_auth_service,
    )

    summary_service = providers.Factory(
        ProviderSummaryService,
        settings=config,
        resource_tracker=resource_tracker,
        vm_service=vm_application_service,
        certificate_service=certificate_maintenance_service,
    )

    provider_settings_service = providers.Factory(
        ProviderSettingsService,
        settings=config,
        resource_tracker=resource_tracker,
        broadcaster=provider_event_broadcaster,
    )

    provider_live_service = providers.Singleton(
        ProviderLiveService,
        broadcaster=provider_event_broadcaster,
        provider_info_service=provider_info_service,
        summary_service=summary_service,
        vm_application_service=vm_application_service,
        stream_status_service=stream_status_service,
        monitoring_service=monitoring_service,
        webhook_service=webhook_service,
        auth_service=provider_auth_service,
    )
