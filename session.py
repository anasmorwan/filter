import time

session = {
    "chat_history": [], # 👈 هذه هي ذاكرة السياق القصيرة
    "active": False,
    "start_time": None,
    "topic": None,
    "difficulty": "normal",
    "stage": "INTRO",
    "current_question": None,
    "last_ai_message": 0, # أهم متغير الآن
    "topic_progress": 0,
    "learning_goal": None,
    "student_confusion": 0,
    "conversation_stage": "INTRO",
    "stats": {
        "messages_since_last_ai": 0,
        "unique_users": set(),
        "questions_count": 0,
        "answers_count": 0,
        "last_message_time": 0
    }
}

def start_session(topic="general", difficulty="normal"):
    session["active"] = True
    session["topic"] = topic
    session["difficulty"] = difficulty
    session["start_time"] = time.time()
    session["last_ai_message"] = time.time() # نعتبر أن البوت بدأ الآن
    
    # تفريغ الإحصائيات للجلسة الجديدة
    session["stats"]["messages_since_last_ai"] = 0
    session["stats"]["unique_users"] = set()

    print("\n=== SESSION STARTED ===")
    print("Topic:", topic)
    print("Difficulty:", difficulty)

def stop_session():
    session["active"] = False
    print("\n=== SESSION STOPPED ===")

def session_is_active():
    return session["active"]

def get_session_info():
    return session

def set_current_question(question):
    session["current_question"] = question

def update_ai_timestamp():
    """هذه الدالة سنستدعيها كلما تحدث الذكاء الاصطناعي"""
    session["last_ai_message"] = time.time()
    session["stats"]["messages_since_last_ai"] = 0
    
def get_session_minutes():
    """تحسب عدد الدقائق التي مرت منذ بداية الجلسة"""
    if not session["active"] or session["start_time"] is None:
        return 0
    return (time.time() - session["start_time"]) / 60


def get_silence_duration():
    """تحسب كم ثانية مرت منذ آخر مرة نطق فيها البوت"""
    if not session["active"]:
        return 0
    return time.time() - session["last_ai_message"]

# وأضف هذه الدالة في الأسفل:
def add_to_chat_history(speaker, text):
    """تحفظ آخر 15 رسالة للحفاظ على سياق المحادثة"""
    history = session["chat_history"]
    history.append(f"{speaker}: {text}")
    
    # نكتفي بآخر 15 رسالة حتى لا يتجاوز الـ AI الحد الأقصى للتوكنز (Tokens)
    if len(history) > 15:
        history.pop(0)

def get_chat_history():
    return "\n".join(session["chat_history"])
