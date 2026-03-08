# buffer.py

import time
from collections import deque
from session import get_session_info



MAX_BUFFER_SIZE = 100

message_buffer = deque(maxlen=MAX_BUFFER_SIZE)
last_window_time = time.time()


message_queue = deque(maxlen=50)
last_processing_time = time.time()
WINDOW_SECONDS = 15  # default


def get_buffer():
    return list(message_buffer)


def clear_buffer():
    message_buffer.clear()


def should_process_window():
    global last_processing_time, WINDOW_SECONDS
    session = get_session_info()
    WINDOW_SECONDS = session.get("window_seconds", WINDOW_SECONDS)
    return time.time() - last_processing_time >= WINDOW_SECONDS

def pop_window_messages():
    global last_processing_time
    messages = list(message_queue)
    message_queue.clear()
    last_processing_time = time.time()
    return messages

def add_message(msg):
    message_queue.append(msg)


def get_recent_messages(n=5):
    return list(message_queue)[-n:]
