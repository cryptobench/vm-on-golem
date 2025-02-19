#!/usr/bin/env python3
import uvicorn
import os
from dotenv import load_dotenv
from discovery.config import settings

# Load environment variables from .env file
load_dotenv()

def main():
    """Run the discovery server."""
    uvicorn.run(
        "discovery:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )

if __name__ == "__main__":
    main()
