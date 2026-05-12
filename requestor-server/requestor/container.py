from dependency_injector import containers, providers
from golem_base_sdk import GolemBaseClient

from requestor.config import config
from requestor.db.session import make_session_factory, make_sqlite_engine
from requestor.discovery.backends import ArkivDiscoveryClient, CentralDiscoveryClient
from requestor.discovery.service import ProviderDiscoveryService
from requestor.payments.service import RequestorPaymentService
from requestor.provider_client.factory import ProviderClientFactory
from requestor.services.database_service import DatabaseService
from requestor.services.ssh_service import SSHService
from requestor.vm.application_service import VMApplicationService
from requestor.vm.repo import VMRepository
from requestor.wallet.service import WalletService


class Container(containers.DeclarativeContainer):
    """Dependency injection container for the requestor service."""

    settings = providers.Object(config)

    engine = providers.Singleton(
        make_sqlite_engine,
        db_path=settings.provided.db_path,
    )
    session_factory = providers.Singleton(make_session_factory, engine=engine)
    vm_repo = providers.Factory(VMRepository, session_factory=session_factory)

    arkiv_discovery_client = providers.Singleton(
        ArkivDiscoveryClient,
        client_factory=GolemBaseClient,
    )
    central_discovery_client = providers.Factory(
        CentralDiscoveryClient,
    )
    discovery_service = providers.Factory(
        ProviderDiscoveryService,
        settings=settings,
        arkiv_client=arkiv_discovery_client,
        central_client=central_discovery_client,
    )

    provider_client_factory = providers.Factory(
        ProviderClientFactory,
        settings=settings,
    )
    payment_service = providers.Factory(
        RequestorPaymentService,
        settings=settings,
        vm_repo=vm_repo,
        provider_client_factory=provider_client_factory,
    )
    vm_application_service = providers.Factory(
        VMApplicationService,
        settings=settings,
        vm_repo=vm_repo,
        discovery_service=discovery_service,
        provider_client_factory=provider_client_factory,
        payment_service=payment_service,
    )
    wallet_service = providers.Factory(WalletService, settings=settings)

    # Compatibility providers for the old CLI-facing modules.
    database_service = providers.Factory(
        DatabaseService, db_path=settings.provided.db_path
    )
    ssh_service = providers.Factory(SSHService, key_dir=settings.provided.ssh_key_dir)
