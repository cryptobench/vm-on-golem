import logging

from .app import create_app
from .config import Settings, load_environment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

load_environment()
app = create_app()


def start() -> None:
    import uvicorn

    load_environment()
    settings = Settings()
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"][
        "fmt"
    ] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logger.info("Starting port checker server on %s:%s", settings.host, settings.port)
    uvicorn.run(
        "port_checker.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
        log_config=log_config,
        timeout_keep_alive=60,
        limit_concurrency=100,
    )


if __name__ == "__main__":
    start()
