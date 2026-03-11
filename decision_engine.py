import time
from collections import Counter
from session import get_session_info, update_ai_timestamp, get_session_minutes


MIN_AI_COOLDOWN = 5
SILENCE_HINT_TIME = 10
NEW_QUESTION_TIME = 25

COOLDOWN = 8
SILENCE_LIMIT = 20
THRESHOLD = 90


def analyze_messages(messages):

    stats = {
        "total": 0,
        "questions": 0,
        "answers": 0,
        "short_answers": 0,
        "reactions": 0,
        "confidence_sum": 0,
        "unique_users": set(),
        "answers_count": 0  # تمت إضافته بدون حذف أي متغير
    }

    for m in messages:

        msg_type = m.get("type")
        conf = m.get("confidence", 0.7)

        stats["total"] += 1
        stats["confidence_sum"] += conf
        stats["unique_users"].add(m["user_id"])

        if msg_type == "question":
            stats["questions"] += conf

        elif msg_type == "answer":
            stats["answers"] += conf
            stats["answers_count"] += 1

        elif msg_type == "short_answer":
            stats["short_answers"] += conf
            stats["answers_count"] += 1

        elif msg_type == "reaction":
            stats["reactions"] += conf

    stats["unique_users"] = len(stats["unique_users"])

    return stats


def estimate_confusion(stats):

    confusion = 0

    if stats["questions"] > 1:
        confusion += 3

    if stats["short_answers"] > stats["answers"]:
        confusion += 2

    if stats["reactions"] > stats["answers"]:
        confusion += 1

    if stats["answers"] == 0 and stats["questions"] > 0:
        confusion += 2

    return min(confusion, 10)


def calculate_priority(stats, session, time_since_ai):

    score = 0

    # الصمت
    if stats["total"] == 0:
        score += (time_since_ai / SILENCE_LIMIT) * 120

    # الأسئلة أهم شيء في الحصة
    score += stats["questions"] * 50

    # الإجابات
    score += stats["answers"] * 25

    # الردود القصيرة
    score += stats["short_answers"] * 15

    # التفاعل السطحي يقلل تدخل AI
    score -= stats["reactions"] * 5

    # نشاط الطلاب
    if stats["unique_users"] >= 3:
        score -= 25

    # تقدم الموضوع
    progress = session.get("topic_progress", 0)
    score += progress * 0.4

    # ارتباك الطلاب
    confusion = session.get("student_confusion", 0)
    score += confusion * 12

    # مرور الوقت
    score += min(time_since_ai * 1.3, 60)

    return score



def decide_next_action(messages):
    mode = session.get("mode", "conversation")
    session = get_session_info()
    stage = session.get("stage", "INTRO")
    
    session_minutes = get_session_minutes()

    now = time.time()

    # حماية من last_ai_message غير المهيأ
    last_ai = session.get("last_ai_message", now)

    time_since_ai = now - last_ai
    time_since_ai = max(0, min(time_since_ai, 120))

    if time_since_ai < COOLDOWN:
        return "WAIT"

    stats = analyze_messages(messages)

    confusion = estimate_confusion(stats)
    session["student_confusion"] = confusion

    priority = calculate_priority(stats, session, time_since_ai)

    progress = session.get("topic_progress", 0)

    print(
        f"[AI Brain] score={priority:.1f} "
        f"questions={stats['questions']:.1f} "
        f"answers={stats['answers']:.1f} "
        f"users={stats['unique_users']} "
        f"confusion={confusion}"
    )

    if priority < THRESHOLD:
        return "WAIT"

    update_ai_timestamp()
    # ---------------------------------------------------------
    # النموذج الأول: المحادثة الحرة (الكود القديم الخاص بك)
    # ---------------------------------------------------------
    if mode == "conversation":
        return decide_conversation_logic(messages, session, stats) # منطقك القديم هنا
        
    # ---------------------------------------------------------
    # النموذج الثاني: المحاضرة الموجهة (Lecture Mode)
    # ---------------------------------------------------------

    elif mode == "lecture":
        return decide_lecture_logic(messages, session, stats) # دالة فرعية للتنظيم



# ---------------------------------------------------------
# دوال النموذجين الاول و الثاني (lecturer & english Teacher)
# ---------------------------------------------------------

def decide_lecture_logic(messages, session, stats): # دالة فرعية للتنظيم
    stage = session.get("stage", "INTRO")
    
    # 1. إذا قاطع الطلاب المحاضرة بسؤال:
    if messages and any(m["type"] == "question" for m in messages):
        return "ANSWER_LECTURE_QUESTION" # يرد على السؤال ثم يربطه بالمحاضرة
        
    # 2. إذا كان الطلاب يجيبون على تمرين أو سؤال طرحه البوت:
    if messages and session["current_stage"] == "CHECK_UNDERSTANDING":
        session["current_stage"] = "EXPLAIN" # نعود للشرح بعد التقييم
        return "EVALUATE_AND_CONTINUE"

    # 3. إذا كان الـ Heartbeat هو من استدعى الدالة (لا توجد رسائل = صمت / وقت الشرح):
    if not messages:
        stage = session["current_stage"]
            
        if stage == "INTRO":
            session["current_stage"] = "EXPLAIN"
            return "INTRODUCE_LECTURE"
                
        elif stage == "EXPLAIN":
            # إذا انتهينا من كل الفقرات
            if session["current_chunk_index"] >= len(session["lecture_chunks"]):
                session["current_stage"] = "OUTRO"
                return "SUMMARIZE_LECTURE"
                
            # إما أن يشرح الفقرة التالية، أو يسأل سؤالاً للتأكد من الفهم
            # مثلاً: بعد كل فقرتين، نطرح سؤالاً (Quiz)
            if session["current_chunk_index"] > 0 and session["current_chunk_index"] % 2 == 0:
                session["current_stage"] = "CHECK_UNDERSTANDING"
                return "ASK_CONCEPT_QUESTION"
            else:
                return "TEACH_NEXT_CHUNK"


def decide_conversation_logic(messages, session, stats): # منطقك القديم هنا
    
    stage = session.get("stage", "INTRO")
    conversation_stage = session.get("conversation_stage", "DISCUSSION")

    session_minutes = get_session_minutes()

    now = time.time()

    # حماية من last_ai_message غير المهيأ
    last_ai = session.get("last_ai_message", now)

    time_since_ai = now - last_ai
    time_since_ai = max(0, min(time_since_ai, 120))

    if not messages:
        return "WAKE_UP_SESSION"

    # --------------------------------
    # مراحل الدرس
    # --------------------------------

    if stage == "INTRO":
        session["stage"] = "WARMUP"
        return "INTRO_LESSON"

    if stage == "WARMUP" and stats["answers"] >= 2:
        session["stage"] = "DISCUSSION"

    # --------------------------------
    # صمت في الصف
    # --------------------------------

    if stats["total"] == 0:

        if time_since_ai > SILENCE_LIMIT:
            return "WAKE_UP_SESSION"

        return "WAIT"

    # --------------------------------
    # أسئلة الطلاب
    # --------------------------------

    if stats["questions"] > 0 and stats["answers"] == 0:
        return "ANSWER_QUESTION"

    if stats["questions"] > 0 and stats["answers"] > 0:
        return "EVALUATE_STUDENT_ANSWERS"

    # --------------------------------
    # متابعة السؤال الحالي
    # --------------------------------

    if session.get("current_question"):

        if stats["answers_count"] >= 3:
            session["current_question"] = None
            return "GIVE_FEEDBACK_ON_ANSWERS"

    # --------------------------------
    # توسيع النقاش
    # --------------------------------

    if stats["answers"] >= 2 and progress < 40:
        session["topic_progress"] = progress + 5
        return "ASK_FOLLOWUP"

    if stats["answers"] >= 2 and progress < 60:
        session["topic_progress"] = progress + 10
        return "ENCOURAGE_DISCUSSION"

    # --------------------------------
    # الطلاب مرتبكون
    # --------------------------------

    if stats["short_answers"] > stats["answers"]:
        return "GIVE_HINT"

    # --------------------------------
    # تلخيص النقاش
    # --------------------------------

    if progress >= 60 and stats["answers"] >= 3:
        session["conversation_stage"] = "SUMMARY"
        return "SUMMARIZE_DISCUSSION"

    if conversation_stage == "SUMMARY":
        session["stage"] = "WARMUP"
        session["topic_progress"] = 0
        session["conversation_stage"] = "DISCUSSION"
        return "ASK_NEW_TOPIC_QUESTION"

    # --------------------------------
    # نهاية الدرس
    # --------------------------------

    if session_minutes > 10:
        return "OUTRO_LESSON"

    if session_minutes > 50 or progress >= 80:

        if stats["questions"] > 0:
            return "ANSWER_QUESTION"

        return "LESSON_WRAPPING_UP"

    # --------------------------------
    # تعليق عام
    # --------------------------------

    return "GENERAL_COMMENT"



