import time
from session import get_session_info


def decide_next_action():

    session = get_session_info()
    stats = session["stats"]

    now = time.time()

    messages = stats["messages_since_last_ai"]
    questions = stats["questions_count"]

    time_since_ai = now - session["last_ai_message"]

    # لا يتكلم بسرعة
    if time_since_ai < 4:
        return "WAIT"

    # إذا سأل الطلاب
    if questions > 0:
        return "ANSWER"

    # الشات نشط
    if messages >= 5:
        return "COMMENT"

    # صمت
    if messages == 0 and time_since_ai > 8:
        return "HINT"

    # تغيير السؤال
    if time_since_ai > 20:
        return "NEW_QUESTION"

    return "WAIT"
