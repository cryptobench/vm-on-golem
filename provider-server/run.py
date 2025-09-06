#!/usr/bin/env python3
import os
import sys
import asyncio
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

from provider.main import cli

if __name__ == "__main__":
    cli()
