#!/usr/bin/env python3
import asyncio
import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from provider.main import cli

if __name__ == "__main__":
    cli()
