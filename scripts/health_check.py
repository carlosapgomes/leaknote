#!/usr/bin/env python3
"""
Health check script for monitoring.
Returns exit code 0 if healthy, 1 if unhealthy.

Usage:
    python scripts/health_check.py
"""

import asyncio
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from db import check_health, close_pool


async def main():
    try:
        # Check database
        if not await check_health():
            print("UNHEALTHY: Database connection failed")
            sys.exit(1)

        print("HEALTHY")
        sys.exit(0)

    except Exception as e:
        print(f"UNHEALTHY: {e}")
        sys.exit(1)

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
