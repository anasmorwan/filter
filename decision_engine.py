# decision_engine.py

import time
from collections import Counter
from session import get_session_info, update_ai_timestamp


MIN_AI_COOLDOWN = 5      # أقل وقت بين ردود AI
SILENCE_HINT_TIME = 10  # وقت الصمت قبل إعطاء hint
NEW_QUESTION_TIME = 25  # وقت تغيير السؤال


def analyze_messages(messages):
    """
    يحلل نافذة الرسائل
    """

    stats = {
        "total": 0,
        "questions": 0,
        "answers": 0,
        "reactions": 0,
        "users": set()
    }

    for msg in messages:

        stats["total"] += 1

        msg_type = msg["type"]

        if msg_type == "question":
            stats["questions"] += 1

        elif msg_type in ["answer", "short_answer"]:
            stats["answers"] += 1

        elif msg_type == "reaction":
            stats["reactions"] += 1

        stats["users"].add(msg["user_id"])

    stats["unique_users"] = len(stats["users"])

    return stats


def evaluate_chat_state(stats):

    """
    يحول الإحصائيات إلى حالة الشات
    """

    if stats["total"] == 0:
        return "silent"

    if stats["questions"] > 0:
        return "students_asking"

    if stats["answers"] >= 3:
        return "students_answering"

    if stats["reactions"] >= stats["answers"]:
        return "low_value_chat"

    return "normal"


def decide_next_action(messages):

    session = get_session_info()

    now = time.time()

    last_ai = session["last_ai_message"]

    time_since_ai = now - last_ai

    mode = session["mode"]

    stats = analyze_messages(messages)

    chat_state = evaluate_chat_state(stats)

    print("\n--- DECISION ENGINE ---")
    print("Mode:", mode)
    print("Chat state:", chat_state)
    print("Messages:", stats["total"])
    print("Unique users:", stats["unique_users"])
    print("-----------------------", flush=True)

    # ---------- cooldown ----------
    if time_since_ai < MIN_AI_COOLDOWN:
        return "WAIT"

    # ---------- students asking ----------
    if chat_state == "students_asking":
        update_ai_timestamp()
        return "ANSWER"

    # ---------- students answering ----------
    if chat_state == "students_answering":

        if stats["unique_users"] >= 2:
            update_ai_timestamp()
            return "COMMENT"

        return "WAIT"

    # ---------- low value chat ----------
    if chat_state == "low_value_chat":
        return "IGNORE"

    # ---------- silence ----------
    if chat_state == "silent":

        if time_since_ai > SILENCE_HINT_TIME:
            update_ai_timestamp()
            return "HINT"

        return "WAIT"

    # ---------- normal flow ----------
    if time_since_ai > NEW_QUESTION_TIME:
        update_ai_timestamp()
        return "NEW_QUESTION"

    return "WAIT"
