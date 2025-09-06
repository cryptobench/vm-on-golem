import os
from dependency_injector import containers, providers
from pathlib import Path

from .config import settings
from .discovery.resource_tracker import ResourceTracker
from .discovery.golem_base_advertiser import GolemBaseAdvertiser
from .discovery.advertiser import DiscoveryServerAdvertiser
from .discovery.service import AdvertisementService
from .service import ProviderService
from .vm.multipass_adapter import MultipassAdapter
from .vm.service import VMService
from .vm.name_mapper import VMNameMapper
from .vm.port_manager import PortManager
from .vm.proxy_manager import PythonProxyManager


class Container(containers.DeclarativeContainer):
    """Dependency injection container."""

    config = providers.Configuration()

    resource_tracker = providers.Singleton(ResourceTracker)

    advertiser = providers.Selector(
        config.ADVERTISER_TYPE,
        golem_base=providers.Singleton(
            GolemBaseAdvertiser,
            resource_tracker=resource_tracker,
        ),
        discovery_server=providers.Singleton(
            DiscoveryServerAdvertiser,
            resource_tracker=resource_tracker,
        ),
    )

    advertisement_service = providers.Singleton(
        AdvertisementService,
        advertiser=advertiser,
    )

    vm_name_mapper = providers.Singleton(
        VMNameMapper,
        db_path=Path(settings.VM_DATA_DIR) / "vm_names.json",
    )

    port_manager = providers.Singleton(
        PortManager,
        start_port=config.PORT_RANGE_START,
        end_port=config.PORT_RANGE_END,
        state_file=providers.Callable(
            os.path.join,
            config.PROXY_STATE_DIR,
            "ports.json"
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

    provider_service = providers.Singleton(
        ProviderService,
        vm_service=vm_service,
        advertisement_service=advertisement_service,
        port_manager=port_manager,
    )
