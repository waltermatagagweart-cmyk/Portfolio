"""
pytest configuration.

asyncpg requires Selector-based sockets; Python's default ProactorEventLoop
on Windows doesn't support them cleanly (connections get torn down against a
closed/mismatched loop between tests, surfacing as noisy AttributeError /
RuntimeError spam during teardown). Switching the event loop policy fixes it.
This only matters on Windows — a no-op everywhere else.
"""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
