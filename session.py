import time

session = {
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

def get_silence_duration():
    """تحسب كم ثانية مرت منذ آخر مرة نطق فيها البوت"""
    if not session["active"]:
        return 0
    return time.time() - session["last_ai_message"]
