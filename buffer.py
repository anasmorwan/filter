# buffer.py

import time
from collections import deque
from session import get_session_info
from difflib import SequenceMatcher


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

    if not message_queue:
        return False

    # معالجة فورية إذا كان هناك سؤال
    if any(m["type"] == "question" for m in message_queue):
        return True

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



# utils.py أو داخل bot.py
def similar(a, b):
    """حساب درجة التشابه بين كلمتين"""
    return SequenceMatcher(None, a, b).ratio()


def should_interrupt(student_msg, session):

    text = student_msg.get("text", "").lower()
    radar_keywords = session.get("priority_keywords", [])

    words = text.split()

    # 1. كلمات الطوارئ المطلقة
    emergency = ["عيد", "لم افهم", "لحظة", "توقف", "wait", "repeat"]

    for e in emergency:
        if e in text:
            return True

    # 2. فحص الرادار مع fuzzy matching
    found_keywords = []

    for keyword in radar_keywords:
        keyword = keyword.lower()

        for w in words:
            if similar(w, keyword) > 0.8:   # نسبة التشابه
                found_keywords.append(keyword)
                break

    if found_keywords:
        print(f"🎯 Radar hit! Student asked about: {found_keywords}")
        return True

    # 3. فحص سؤال طويل
    if len(text) > 30 and "?" in text:
        return True

    return False
