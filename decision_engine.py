# decision_engine.py

import time
from collections import Counter
from session import get_session_info, update_ai_timestamp, get_session_minutes


MIN_AI_COOLDOWN = 5      # أقل وقت بين ردود AI
SILENCE_HINT_TIME = 10  # وقت الصمت قبل إعطاء hint
NEW_QUESTION_TIME = 25  # وقت تغيير السؤال


COOLDOWN = 8       # فترة منع الرد المتكرر
SILENCE_LIMIT = 20 # مدة الصمت قبل التدخل
THRESHOLD = 90     # حد الأولوية للتدخل



def analyze_messages(messages):
    """
    تحليل الرسائل مع استخدام درجة الثقة
    """

    stats = {
        "total": 0,
        "questions": 0,
        "answers": 0,
        "short_answers": 0,
        "reactions": 0,
        "confidence_sum": 0,
        "unique_users": set()
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

        elif msg_type == "short_answer":
            stats["short_answers"] += conf

        elif msg_type == "reaction":
            stats["reactions"] += conf

    stats["unique_users"] = len(stats["unique_users"])

    return stats


def estimate_confusion(stats):
    """
    تقدير مستوى ارتباك الطلاب
    """

    confusion = 0

    if stats["questions"] > 1:
        confusion += 3

    if stats["short_answers"] > stats["answers"]:
        confusion += 2

    if stats["reactions"] > stats["answers"]:
        confusion += 1

    return min(confusion, 10)


def calculate_priority(stats, session, time_since_ai):

    score = 0

    # --- الصمت ---
    if stats["total"] == 0:
        score += (time_since_ai / SILENCE_LIMIT) * 120

    # --- الأسئلة ---
    score += stats["questions"] * 40

    # --- الإجابات ---
    score += stats["answers"] * 20

    # --- ردود قصيرة ---
    score += stats["short_answers"] * 10

    # --- تفاعل سطحي يقلل الأولوية ---
    score -= stats["reactions"] * 10

    # --- نشاط الطلاب ---
    if stats["unique_users"] >= 3:
        score -= 20

    # --- تقدم الموضوع ---
    progress = session.get("topic_progress", 0)
    score += progress * 0.5

    # --- ارتباك الطلاب ---
    confusion = session.get("student_confusion", 0)
    score += confusion * 12

    # --- مرور الوقت ---
    score += time_since_ai * 1.3

    return score


def decide_next_action(messages):

    session = get_session_info()
    stage = session["stage"]
    session_minutes = get_session_minutes()
    now = time.time()
    time_since_ai = now - session["last_ai_message"]

    if time_since_ai < COOLDOWN:
        return "WAIT"

    stats = analyze_messages(messages)

    # تقدير ارتباك الطلاب
    confusion = estimate_confusion(stats)
    session["student_confusion"] = confusion

    priority = calculate_priority(stats, session, time_since_ai)

    stage = session.get("conversation_stage", "DISCUSSION")
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


    if stage == "INTRO":
        session["stage"] = "WARMUP"
        return "INTRO_LESSON"

    if stage == "WARMUP" and stats["answers"] >= 2:
        session["stage"] = "DISCUSSION"


    if stats["total"] == 0:
        return "WAKE_UP_SESSION"

    if stats["answers"] >= 3:
        session["current_question"] = None


    if stats["questions"] > 0 and stats["answers"] == 0:
        return "ANSWER_QUESTION"


    if stats["questions"] > 0 and stats["answers"] > 0:
        return "EVALUATE_STUDENT_ANSWERS"

    if session["current_question"]:

        if stats["answers_count"] >= 3:
            return "GIVE_FEEDBACK_ON_ANSWERS"


    if stats["answers"] >= 2 and progress < 40:
        return "ASK_FOLLOWUP"


    if stats["answers"] >= 2 and progress < 60:
        session["topic_progress"] += 10
        return "ENCOURAGE_DISCUSSION"


    if stats["short_answers"] > stats["answers"]:
        return "GIVE_HINT"


    if progress >= 60 and stats["answers"] >= 3:
        session["conversation_stage"] = "SUMMARY"
        return "SUMMARIZE_DISCUSSION"

    if stage == "DISCUSSION" and session["topic_progress"] >= 60:
        session["stage"] = "SUMMARY"
        return "SUMMARIZE_DISCUSSION"



    if stage == "SUMMARY":
        session["stage"] = "WARMUP"
        session["topic_progress"] = 0
        return "ASK_NEW_TOPIC_QUESTION"


    if session_minutes > 70:
        return "OUTRO_LESSON"

    # ----- منطق نهاية الدرس -----
    if session_minutes > 50 or session["topic_progress"] >= 80:
        # إذا هناك أسئلة معلقة → الرد عليها قبل الإغلاق
        if stats["questions"] > 0:
            return "ANSWER_QUESTION"
        else:
            return "LESSON_WRAPPING_UP"



    return "GENERAL_COMMENT"
