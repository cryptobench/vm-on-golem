#!/usr/bin/env python3
import os
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

def main():
    """Run the provider server."""
    # Load environment variables from .env file
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)

    # Debug: Print environment variables
    print("Environment variables:")
    for key, value in os.environ.items():
        if key.startswith('GOLEM_PROVIDER_'):
            print(f"{key}={value}")

    # Import settings after loading environment variables
    from provider.config import settings

    # Run server
    uvicorn.run(
        "provider:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug"
    )

if __name__ == "__main__":
    main()
