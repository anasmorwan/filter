import time


# دالة جديدة لبدء المحاضرة
def start_lecture_session(topic, text_content):
    session["active"] = True
    session["mode"] = "lecture"
    session["topic"] = topic
    session["current_stage"] = "INTRO"
    session["current_chunk_index"] = 0
    
    # تقسيم النص إلى "لقيمات" (Micro-learning) كل فقرة لوحدها
    # يمكنك تحسين دالة التقسيم لاحقاً لتعتمد على النقاط أو الفواصل
    session["lecture_chunks"] = [chunk for chunk in text_content.split('\n\n') if len(chunk) > 20]
    
    session["start_time"] = time.time()
    session["last_ai_message"] = time.time()




def get_current_stage():
    idx = session["current_stage_index"]
    return session["stages"][idx]

def move_to_next_stage():
    if session["current_stage_index"] < len(session["stages"]) - 1:
        session["current_stage_index"] += 1
        session["stage_start_time"] = time.time()
        return True
    return False














session = {
    "most_accurate_answers": [],
    "bingo_answer_received": False,
    "voice_name": "en-US-AndrewMultilingualNeural",
    "chat_history": [], # 👈 هذه هي ذاكرة السياق القصيرة
    "is_speaking": True,
    "priority_keywords": [],
    "waiting_for_answer": False,
    "pending_questions": [],
    "mode": "conversation",  # 👈 إما 'conversation' أو 'lecture'
    "active": False,
    "start_time": None,
    "topic": None,
    "difficulty": "normal",
    "current_stage_index": 0, # مؤشر المرحلة الحالية
    "response_text": "...",
    "expects_answer": False,
    "class_understanding": "good",
    "stages": [
        {"name": "INTRO", "type": "hook", "min_duration": 2},
        {"name": "ICE_BREAKER", "type": "game", "game_type": "word_association", "min_duration": 3},
        {"name": "CONTENT_FLOW", "type": "teaching", "min_duration": 5},
        {"name": "ACTION_ZONE", "type": "game", "game_type": "guessing_game", "min_duration": 7},
        {"name": "CONFIDENCE_BOOST", "type": "feedback", "min_duration": 3},
        {"name": "COOL_DOWN", "type": "summary", "min_duration": 2}
    ],
    # --- إضافات نموذج المحاضرة (Lesson Plan) ---
    "lecture_chunks": [],       # قائمة تحتوي على فقرات الملف (مقسمة)
    "current_chunk_index": 0,   # أين نحن الآن في الملف؟
    "current_stage": "INTRO",   # مراحل الدرس (INTRO, EXPLAIN, CHECK_UNDERSTANDING, Q&A, OUTRO)
    "questions_asked": 0,       # عدد أسئلة الاختبار التي طرحها البوت
    "stage_start_time": 0,
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

def start_session(topic, difficulty):
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

def get_session_voice_name():
    return session["voice_name"]

def set_session_voice_name(voice_name):
    session["voice_name"] = voice_name
    
