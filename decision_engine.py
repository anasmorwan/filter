# decision_engine.py

import time
from collections import Counter
from session import get_session_info, update_ai_timestamp


MIN_AI_COOLDOWN = 5      # أقل وقت بين ردود AI
SILENCE_HINT_TIME = 10  # وقت الصمت قبل إعطاء hint
NEW_QUESTION_TIME = 25  # وقت تغيير السؤال


COOLDOWN = 8       # فترة منع الرد المتكرر
SILENCE_LIMIT = 20 # مدة الصمت قبل التدخل
THRESHOLD = 90     # حد الأولوية للتدخل

def calculate_priority(stats, time_since_ai, confusion):
    """
    حساب أولوية تدخل المدرس بناءً على النشاط والالتباس
    """
    score = 0

    # الصمت يزيد الرغبة في التدخل
    if stats["total"] == 0:
        score += (time_since_ai / SILENCE_LIMIT) * 120

    # أسئلة الطلاب
    if stats["questions"] > 0:
        if stats["answers"] == 0:
            score += 70
        else:
            score += 30

    # نشاط الطلاب يقلل التدخل
    if stats["unique_users"] >= 3 and stats["answers"] >= 2:
        score -= 40

    # الالتباس يزيد التدخل
    score += confusion * 10

    # مرور الوقت
    score += time_since_ai * 1.2

    return score

def decide_next_action(messages):
    session = get_session_info()
    now = time.time()
    time_since_ai = now - session["last_ai_message"]

    # --- جمع إحصاءات الطلاب ---
    stats = {
        "total": len(messages),
        "questions": sum(1 for m in messages if m["type"] == "question"),
        "answers": sum(1 for m in messages if m["type"] in ["answer","short_answer"]),
        "unique_users": len(set(m["user_id"] for m in messages))
    }

    # --- متغيرات الحالة التعليمية ---
    confusion = session.get("student_confusion", 0)           # 0-10
    stage = session.get("conversation_stage", "DISCUSSION")   # مرحلة الدرس
    progress = session.get("topic_progress", 0)               # 0-100%
    goal = session.get("learning_goal", "general topic")

    # --- فترة التبريد ---
    if time_since_ai < COOLDOWN:
        return "WAIT"

    priority_score = calculate_priority(stats, time_since_ai, confusion)
    print(f"[AI Brain] Score: {priority_score:.1f} | Stage: {stage} | Progress: {progress}% | Confusion: {confusion}")

    if priority_score >= THRESHOLD:
        update_ai_timestamp()

        # --- اتخاذ القرار بحسب مرحلة الدرس ---
        if stage == "INTRO":
            return "ASK_INITIAL_QUESTION"

        if stage == "DISCUSSION":
            if stats["questions"] > 0 and stats["answers"] == 0:
                return "ANSWER_QUESTION"
            if stats["answers"] >= 2:
                return "EVALUATE_STUDENT_ANSWERS"
            return "GENERAL_COMMENT"

        if stage == "CORRECTION":
            return "CORRECT_MISTAKES"

        if stage == "SUMMARY":
            return "SUMMARIZE_AND_NEXT"

        if stage == "NEXT_TOPIC":
            return "ASK_NEXT_TOPIC_QUESTION"

    return "WAIT"
