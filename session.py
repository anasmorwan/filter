import time

session = {
    "active": False,
    "topic": None,
    "difficulty": "normal",
    "stage": "INTRO",
    "current_question": None,
    "last_ai_message": 0,
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


def get_session_mode():
    return session["mode"]


def set_session_mode(mode):
    session["mode"] = mode


def set_current_question(question):
    session["current_question"] = question


def register_student_message():
    session["messages_since_last_ai"] += 1


def update_ai_timestamp():
    session["last_ai_message"] = time.time()
    session["messages_since_last_ai"] = 0

def update_chat_stats(user_id, text):

    stats = session["stats"]

    stats["messages_since_last_ai"] += 1

    stats["unique_users"].add(user_id)

    stats["last_message_time"] = time.time()

    if "?" in text:
        stats["questions_count"] += 1
