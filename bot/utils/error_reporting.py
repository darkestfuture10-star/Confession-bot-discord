import asyncio
import logging

import aiohttp
import discord


class DiscordWebhookLogHandler(logging.Handler):
    """Queues ERROR+ log records and relays them to a private Discord webhook
    via a background task, so error reporting never blocks whatever code
    raised the error in the first place. Failures to deliver an alert are
    swallowed on purpose — we never want the alerting mechanism itself to
    become a new source of crashes."""

    def __init__(self, webhook_url: str, level=logging.ERROR):
        super().__init__(level=level)
        self.webhook_url = webhook_url
        self._queue: asyncio.Queue[str] | None = None
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """Call once the event loop is running (e.g. in setup_hook)."""
        self._queue = asyncio.Queue()
        self._task = asyncio.create_task(self._worker())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()

    def emit(self, record: logging.LogRecord) -> None:
        if self._queue is None:
            return  # Not started yet (e.g. an error before setup_hook) — drop rather than crash.
        try:
            message = self.format(record)
        except Exception:
            return
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            pass

    async def _worker(self) -> None:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(self.webhook_url, session=session)
            while True:
                message = await self._queue.get()
                chunk = message if len(message) <= 1900 else message[:1900] + "...(truncated)"
                try:
                    await webhook.send(f"```\n{chunk}\n```", username="Confession Bot Errors")
                except Exception:
                    pass