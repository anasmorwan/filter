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



def should_interrupt(msg, session):
    text = msg["text"].lower()
    
    # 1. كلمات الطوارئ (توقف الشرح فوراً)
    emergency_keywords = ["لم افهم", "ما فهمت", "ممكن تعيد", "وضح اكثر", "عيد", "slow down"]
    if any(word in text for word in emergency_keywords):
        return True

    # 2. طول السؤال (الأسئلة العميقة غالباً تكون أطول من 15 حرف)
    if len(text) > 15:
        return True

    # 3. تكرار السؤال (إذا سأل أكثر من طالب نفس الشيء - يعبر عن ارتباك جماعي)
    # يمكن تطوير هذا لاحقاً باستخدام Counter
    
    return False
