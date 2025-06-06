import typer
import asyncio
from app.orchestrators.proxy.prolog_proxy import PrologProxyOrchestrator
from app.core.db import get_async_session
from app.core.logging_config import setup_logging
import logging

app = typer.Typer()


@app.command()
def prolong():
    """Prolong expired proxies"""
    print("!=== LOGGING DEBUG ===!")
    print(logging.getLogger().handlers)

    async def run():
        session_gen = get_async_session()
        session = await session_gen.__anext__()

        try:
            proxy_prolong_orchestrator = PrologProxyOrchestrator(session)
            await proxy_prolong_orchestrator.execute()
        finally:
            await session_gen.aclose()
    asyncio.run(run())
