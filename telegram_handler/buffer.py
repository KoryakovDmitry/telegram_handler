from threading import Event


class MessageBuffer:
    """Buffer for storing and managing log messages."""

    def __init__(self, max_size):
        self.max_size = max_size
        self.buffer = ""
        self.lock = Event()

    def write(self, message):
        if len(self.buffer) + len(message) <= self.max_size:
            self.buffer += message
        else:
            self.flush()

    def read(self, size):
        message = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return message

    def flush(self):
        self.buffer = ""
