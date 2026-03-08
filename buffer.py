# buffer.py

import time
from collections import deque

WINDOW_SECONDS = 15
MAX_BUFFER_SIZE = 100

message_buffer = deque(maxlen=MAX_BUFFER_SIZE)
last_window_time = time.time()


def add_message(msg):
    """
    msg structure:
    {
        "user_id": int,
        "user": str,
        "text": str,
        "type": str,
        "time": float
    }
    """
    message_buffer.append(msg)


def get_buffer():
    return list(message_buffer)


def clear_buffer():
    message_buffer.clear()


def should_process_window():

    global last_window_time

    now = time.time()

    if now - last_window_time >= WINDOW_SECONDS:
        last_window_time = now
        return True

    return False


def pop_window_messages():
    """
    returns all messages then clears buffer
    """
    messages = list(message_buffer)
    message_buffer.clear()
    return messages
