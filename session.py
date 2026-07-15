import time



# 3. تحويل بدء المحاضرة إلى دالة Async لدعم تلخيص الـ AI
async def start_lecture_session(extracted_chunks, full_text):
    from ai import generate_global_summary
    
    # تجهيز البيانات أولاً (بدون تفعيل الجلسة)
    session["mode"] = "lecture"
    session["persona"] = "professor"
    session["current_stage"] = "INTRO"
    session["current_chunk_index"] = 0
    
    # حفظ الـ Chunks المجهزة قبل استدعاء الـ AI
    session["lecture_chunks"] = extracted_chunks
    
    # الآن ننتظر الذكاء الاصطناعي (أثناء هذا الانتظار، المهام الخلفية لن تتدخل لأن active=False)
    goals_summary = await generate_global_summary(full_text)
    session["lecture_goals"] = goals_summary

    # بعد اكتمال كل شيء، نقوم بتفعيل الجلسة وبدء العدادات
    session["start_time"] = time.time()
    session["last_ai_message"] = time.time()
    session["active"] = True  # 🟢 يتم تفعيلها هنا فقط لتجنب التداخل





def get_current_stage():
    idx = session["current_stage_index"]
    return session["stages"][idx]

def move_to_next_stage():
    if session["current_stage_index"] < len(session["stages"]) - 1:
        session["current_stage_index"] += 1
        session["stage_start_time"] = time.time()
        return True
    return False


def get_stage_elapsed_minutes():
    return (time.time() - session["stage_start_time"]) / 60











session = {
    "urgent_questions": [],
    "deferred_questions": [],
    "lecture_goals": [],
    "Bingo_Keywords": [],
    "bingo_answer_received": False,
    "voice_name": "en-US-GuyNeural",
    "chat_history": [], # 👈 هذه هي ذاكرة السياق القصيرة
    "is_speaking": False,
    "priority_keywords": [],
    "waiting_for_answer": False,
    "pending_questions": [],
    "mode": "conversation",  # 👈 إما 'conversation' أو 'lecture'
    "persona": "coach",
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
    session["mode"] = "conversation"
    session["stage_start_time"] = time.time()
    session["current_stage_index"] = 0
    session["persona"] = "coach"
    session["active"] = True
    session["topic"] = topic
    session["difficulty"] = difficulty
    session["start_time"] = time.time()
    session["last_ai_message"] = time.time()
    
    # 👈 تأكيد مسح الذاكرة عند بدء جلسة جديدة
    session["chat_history"] = [] 
    
    # تفريغ الإحصائيات للجلسة الجديدة
    session["stats"]["messages_since_last_ai"] = 0
    session["stats"]["unique_users"] = set()

    print("\n=== SESSION STARTED ===")
    print("Topic:", topic)
    print("Difficulty:", difficulty)

# داخل session.py
def stop_session():
    from documents_handler import clear_old_assets
    # تنظيف شامل لكل بيانات المحاضرة والمود والذاكرة
    session.update({
        "active": False,
        "mode": "conversation", # العودة للوضع الافتراضي
        "lecture_chunks": [],
        "current_chunk_index": 0,
        "lecture_started": False,
        "lecture_goals": None,
        "waiting_for_answer": False,
        "pending_questions": [],
        "urgent_questions": [],       # 👈 تصفير الأسئلة العاجلة القديمة
        "deferred_questions": [],     # 👈 تصفير الأسئلة المؤجلة
        "chat_history": [],           # 👈 (الأهم) مسح ذاكرة المحادثة لكي لا يتذكر المحاضرة
        "current_question": None,     # 👈 إزالة أي سؤال كان ينتظر إجابته
        "bingo_answer_received": False
    })
    
    try:
        clear_old_assets()
    except:
        pass
    print("🧹 Session data, queues, and chat history cleared! Reset to conversation mode.")



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

def change_ai_voice(voice_name):
    session["voice_name"] = voice_name
    
