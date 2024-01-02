from typing import Union
import logging
from time import sleep
import requests
from threading import Thread, RLock
from retry import retry
from telegram_handler.buffer import MessageBuffer
from telegram_handler.consts import (
    API_URL,
    RETRY_COOLDOWN_TIME,
    MAX_RETRYS,
    MAX_MESSAGE_SIZE,
    FLUSH_INTERVAL,
    RETRY_BACKOFF_TIME,
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
    def __init__(
        self,
        bot_token: str,
        channel: Union[str, int],
        level=logging.NOTSET,
    ):
        super().__init__(level)
        self.chat_id = channel
        self._url = TelegramLoggingHandler._format_url(bot_token)
        self._buffer = MessageBuffer(MAX_BUFFER_SIZE)
        self._stop_signal = RLock()
        self._writer_thread = None
        self._start_writer_thread()

    @staticmethod
    def _format_url(bot_token: str):
        return API_URL.format(bot_token=bot_token)

    @retry(
        requests.exceptions.RequestException,
        tries=MAX_RETRYS,
        delay=RETRY_COOLDOWN_TIME,
        backoff=RETRY_BACKOFF_TIME,
        logger=logger,
    )
    def write(self, message):
        response = requests.post(
            self._url,
            data={"text": message, "chat_id": self.chat_id, "parse_mode": "HTML"},
        )

        response.raise_for_status()
        if response.status_code == requests.codes.too_many_requests:
            raise requests.exceptions.RequestException("Too many requests")

    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)
        self._buffer.write(f"{message}.\n")

    def close(self):
        with self._stop_signal:
            self._writer_thread.join()

    def _write_manager(self):
        while True:
            # as long as we can aquire the lock, we can continue
            lock_status = self._stop_signal.acquire(blocking=False)
            if not lock_status:
                break
            else:
                self._stop_signal.release()

            sleep(FLUSH_INTERVAL)
            message = self._buffer.read(MAX_MESSAGE_SIZE)
            if message != "":
                self.write(message)

    def _start_writer_thread(self):
        self._writer_thread = Thread(target=self._write_manager)
        self._writer_thread.daemon = True
        self._writer_thread.start()
