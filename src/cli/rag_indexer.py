"""Run the standalone course-KB indexing worker.

Use --once for a bounded batch in local development or CI. Use --watch only
from a supervised process manager such as systemd.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from src.db import SessionLocal
from src.services.rag import run_index_worker_forever, run_index_worker_once


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process queued Zito RAG index jobs.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Process one finite batch (the default).")
    mode.add_argument("--watch", action="store_true", help="Keep polling for jobs; use under systemd.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum jobs per batch (default: 20).")
    arguments = parser.parse_args()
    if arguments.limit < 1:
        parser.error("--limit must be at least 1")
    return arguments


async def _run(arguments: argparse.Namespace) -> int:
    if arguments.watch:
        await run_index_worker_forever(SessionLocal, limit=arguments.limit)
        return 0

    outcomes = await run_index_worker_once(SessionLocal, limit=arguments.limit)
    print(
        json.dumps(
            {
                "processed": len(outcomes),
                "succeeded": sum(item.status == "succeeded" for item in outcomes),
                "retry": sum(item.status == "retry" for item in outcomes),
                "failed": sum(item.status == "failed" for item in outcomes),
                "superseded": sum(item.status == "superseded" for item in outcomes),
            }
        )
    )
    return 0


def main() -> int:
    return asyncio.run(_run(_parse_arguments()))


if __name__ == "__main__":
    raise SystemExit(main())
