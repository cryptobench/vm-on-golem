#!/usr/bin/env python3
import uvicorn
from dotenv import load_dotenv
from central_discovery.config import settings

# Load environment variables from .env file (if present)
load_dotenv()

def main():
    """Run the central discovery server."""
    uvicorn.run(
        "central_discovery:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )

if __name__ == "__main__":
    main()
