import asyncio
import logging
from threading import Thread, Event
from time import sleep

from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    AIORateLimiter,
)
from telegram_handler.buffer import MessageBuffer
from telegram_handler.consts import (
    MAX_MESSAGE_SIZE,
    FLUSH_INTERVAL,
    MAX_BUFFER_SIZE,
)

logger = logging.getLogger(__name__)


class TelegramFormatter(logging.Formatter):
    """TelegramFormatter."""

    EMOJI_MAP = {
        logging.DEBUG: "DEBUG: \u26aa",
        logging.INFO: "INFO: \U0001f535",
        logging.WARNING: "WARNING: \U0001F7E0",
        logging.ERROR: "ERROR: \U0001F534",
        logging.CRITICAL: "CRITICAL: \U0001f525",
    }

    def __init__(
        self,
        fmt: str = "%(asctime)s - %(levelname)s - %(message)s",
        datefmt: str = None,
        use_emoji: bool = True,
        emoji_map: dict = None,
    ):
        """:fmt: str, default: '%(asctime)s - %(levelname)s - %(message)s'\n
        :datefmt: str, default: None\n
        :use_emoji: bool, default: True\n
        :emoji_map: dict, default: None\n
        """
        super().__init__(fmt, datefmt)
        self.use_emoji = use_emoji
        self.emojis = self.EMOJI_MAP
        if emoji_map:
            self.emojis.update(emoji_map)

    def format(self, record):
        if self.use_emoji and record.levelno in self.emojis:
            record.levelname = self.emojis[record.levelno]
        return super().format(record)


class TelegramLoggingHandler(logging.Handler):
    """Logging handler that sends messages to a Telegram chat."""

    def __init__(self, bot_token, chat_id, level=logging.NOTSET):
        super().__init__(level)
        self.application = (
            ApplicationBuilder()
            .token(bot_token)
            .read_timeout(120)
            .write_timeout(120)
            .concurrent_updates(True)
            .rate_limiter(AIORateLimiter(max_retries=5))
            .http_version("1.1")
            .get_updates_http_version("1.1")
            .build()
        )
        self.chat_id = chat_id
        self._buffer = MessageBuffer(MAX_BUFFER_SIZE)
        self._stop_event = Event()
        self._writer_thread = Thread(target=self._write_manager, daemon=True)
        self._writer_thread.start()

    def emit(self, record):
        message = self.format(record)
        self._buffer.write(f"{message}\n")

    def _write_manager(self):
        while not self._stop_event.is_set():
            sleep(FLUSH_INTERVAL)
            message = self._buffer.read(MAX_MESSAGE_SIZE)
            if message:
                try:
                    asyncio.run(self.async_send_message(message))
                except TelegramError as e:
                    logging.error(f"Failed to send message: {e}")

    async def async_send_message(self, message):
        try:
            await self.application.bot.send_message(
                chat_id=self.chat_id, text=message, parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Failed to send message: {e}")

    def close(self):
        self._stop_event.set()
        self._writer_thread.join()
        super().close()
