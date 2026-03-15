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
        "answers_count": 0  
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
    if stats["questions"] > 1: confusion += 3
    if stats["short_answers"] > stats["answers"]: confusion += 2
    if stats["reactions"] > stats["answers"]: confusion += 1
    if stats["answers"] == 0 and stats["questions"] > 0: confusion += 2
    return min(confusion, 10)


def calculate_priority(stats, session, time_since_ai):
    score = 0
    if stats["total"] == 0: score += (time_since_ai / SILENCE_LIMIT) * 120
    score += stats["questions"] * 50
    score += stats["answers"] * 25
    score += stats["short_answers"] * 15
    score -= stats["reactions"] * 5
    if stats["unique_users"] >= 3: score -= 25
    
    progress = session.get("topic_progress", 0)
    score += progress * 0.4
    confusion = session.get("student_confusion", 0)
    score += confusion * 12
    score += min(time_since_ai * 1.3, 60)
    return score


def decide_next_action(messages):
    session = get_session_info()
    mode = session.get("mode", "conversation")
    now = time.time()

    last_ai = session.get("last_ai_message", now)
    time_since_ai = max(0, min(now - last_ai, 120))

    # لا نتدخل إذا كان الـ AI قد تحدث للتو (إلا لو كان سؤالاً طارئاً)
    has_questions = any(m.get("type") == "question" for m in messages)
    if time_since_ai < COOLDOWN and not has_questions:
        return "WAIT"

    stats = analyze_messages(messages)
    session["student_confusion"] = estimate_confusion(stats)

    # ---------------------------------------------------------
    # النموذج الأول: المحاضرة الموجهة (Lecture Mode)
    # ---------------------------------------------------------
    if mode == "lecture":
        # في وضع المحاضرة، نتجاوز الـ THRESHOLD لأننا نعتمد على هيكل المحاضرة والوقت
        action = decide_lecture_logic(messages, session, stats)
        
        # طباعة شفافة لمعرفة تفكير المحرك
        print(f"🧠 [Engine - Lecture] Decided Action: {action}")
        
        if action != "WAIT":
            update_ai_timestamp()
        return action

    # ---------------------------------------------------------
    # النموذج الثاني: المحادثة الحرة (Conversation Mode)
    # ---------------------------------------------------------
    elif mode == "conversation":
        priority = calculate_priority(stats, session, time_since_ai)
        print(f"[AI Brain] score={priority:.1f} questions={stats['questions']:.1f}")
        
        if priority < THRESHOLD:
            return "WAIT"
            
        action = decide_conversation_logic(messages, session, stats)
        if action != "WAIT":
            update_ai_timestamp()
        return action


# ---------------------------------------------------------
# منطق اتخاذ القرار لوضع المحاضرة (The Brain)
# ---------------------------------------------------------

def decide_lecture_logic(messages, session, stats):
    waiting = session.get("waiting_for_answer", False)
    bingo = session.get("bingo_answer_received", False)
    has_questions = stats["questions"] > 0
    current_index = session.get("current_chunk_index", 0)
    chunks = session.get("lecture_chunks", [])


    # 4. 🌟 السحر هنا: تدفق المحاضرة الطبيعي مع وجود أسئلة
    if has_questions:
        print("🧠 -> Question detected. AI will answer AND teach the next chunk.")
        session["pending_questions"] = [] # تفريغ الأسئلة المعلقة لأننا أرسلناها للذكاء
        return "ANSWER_AND_TEACH"



    # 2. أولوية عالية: الضربة الصائبة (طالب جاوب إجابة نموذجية بسرعة)
    if bingo:
        print("🧠 -> Bingo triggered! Evaluating excellent answer.")
        return "PRAISE_AND_CONTINUE"

    # 3. نحن ننتظر إجابة (المدرس سأل سؤالاً للتو)
    if waiting:
        if messages:
            # هناك رسائل (وليست أسئلة، إذن هي محاولات إجابة)
            print("🧠 -> Students attempted to answer. Evaluating...")
            return "EVALUATE_AND_CONTINUE"
        else:
            # صمت تام وانتهى وقت الـ Heartbeat (لم يجب أحد)
            print("🧠 -> Timeout. No one answered. Teacher will explain and move on.")
            return "ANSWER_AND_CONTINUE"


        
    # ب. هل نحن في البداية تماماً؟
    if current_index == 0 and not session.get("lecture_started"):
        session["lecture_started"] = True
        print("🧠 -> Starting the lecture for the first time.")
        return "INTRODUCE_LECTURE"

    # 2. هل انتهت الشرائح كلها؟
    if current_index >= len(chunks):
        if has_questions: 
            session["pending_questions"] = [] # تفريغ الأسئلة
            return "ANSWER_PENDING_QUESTIONS"
        print("🧠 -> Reached the end of chunks. Summarizing.")
        return "SUMMARIZE_LECTURE"


    # 5. إذا كان هناك رسائل تفاعل عادية (مثل "نعم"، "أكمل") ولا ننتظر إجابة
    print(f"🧠 -> Advancing to chunk {current_index + 1}.")
    return "TEACH_NEXT_CHUNK"
    """
    # د. الانتقال الطبيعي للشريحة التالية
     print(f"🧠 -> Advancing to chunk {current_index + 1}.")
     return "TEACH_NEXT_CHUNK"

"""


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

    if conversation_stage == "INTRO":
        session["conversation_stage"] = "WARMUP"
        return "INTRO_LESSON"

    if conversation_stage == "WARMUP" and stats["answers"] >= 2:
        session["conversation_stage"] = "DISCUSSION"

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



