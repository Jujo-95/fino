"""Run one durable analysis queue cycle outside the HTTP process.

Cloud Run Jobs or another scheduler can invoke this module periodically. The
queue and workspace must be on durable shared storage in multi-instance mode.
"""
import asyncio
from .api.container import AppContainer


async def main() -> None:
    container = AppContainer()
    try:
        await container.jobs.analysis.run_once()
    finally:
        await container.jobs.shutdown()
        await container.chat.shutdown()
        container.close()


if __name__ == '__main__':
    asyncio.run(main())
