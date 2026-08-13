from __future__ import annotations

import asyncio
import sys

# Psycopg's asynchronous Windows transport requires a selector loop. Keep this
# policy scoped to the live CockroachDB suite so ordinary unit tests retain the
# platform default.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
