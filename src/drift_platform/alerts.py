"""Bounded asynchronous, at-least-once webhook delivery."""

import asyncio
import logging
import httpx
from drift_platform.storage import Store

LOGGER = logging.getLogger(__name__)


async def deliver(store: Store, webhook: str | None) -> None:
    """Retry pending alerts; consumers deduplicate the stable idempotency key."""
    if webhook is None:
        return
    async with httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False) as client:
        for identifier, payload, attempts in await asyncio.to_thread(store.pending):
            success = False
            for retry in range(3):
                try:
                    response = await client.post(webhook, content=payload,
                        headers={"Content-Type": "application/json", "Idempotency-Key": f"drift-{identifier}"})
                    response.raise_for_status()
                    success = True
                except httpx.HTTPError:
                    LOGGER.warning("Alert delivery failed for report %s attempt %s", identifier, attempts + retry + 1)
                await asyncio.to_thread(store.attempted, identifier, success)
                if success:
                    break
                if retry < 2:
                    await asyncio.sleep(2 ** retry)

