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
def decide_game_action(game_type, stats, session):
    if game_type == "word_association":
        return "WORD_ASSOCIATION_TURN"
    if game_type == "guessing_game":
        return "GUESSING_GAME_TURN"
    return "GENERAL_COMMENT"


def decide_lecture_logic(messages, session, stats):
    waiting = session.get("waiting_for_answer", False)
    bingo = session.get("bingo_answer_received", False)
    has_questions = stats["questions"] > 0
    current_index = session.get("current_chunk_index", 0)
    chunks = session.get("lecture_chunks", [])
    deferred_qs = session.get("deferred_questions", [])



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
        if has_questions or deferred_qs:
            return "FINAL_Q_AND_A"
            
            session["pending_questions"] = [] # تفريغ الأسئلة
            
            return "ANSWER_PENDING_QUESTIONS"
        print("🧠 -> Reached the end of chunks. Summarizing.")
        return "SUMMARIZE_LECTURE"


    # 5. إذا كان هناك رسائل تفاعل عادية (مثل "نعم"، "أكمل") ولا ننتظر إجابة
    print(f"🧠 -> Advancing to chunk {current_index + 1}.")
    return "TEACH_NEXT_CHUNK"

def decide_conversation_logic(messages, session, stats):
    from session import get_current_stage, move_to_next_stage, get_stage_elapsed_minutes

    stage = get_current_stage()
    stage_type = stage["type"]
    elapsed = get_stage_elapsed_minutes()

    ready_to_advance = elapsed >= stage["min_duration"] and stats["answers_count"] >= 2
    force_advance = elapsed >= stage["min_duration"] * 2

    if (ready_to_advance or force_advance) and stage_type != "summary":
        if move_to_next_stage():
            stage = get_current_stage()
            stage_type = stage["type"]
            print(f"🧠 -> Stage advanced to {stage['name']}")

    # 🟢 امسح "if not messages: return WAKE_UP_SESSION" من هنا تماماً
    # وخلي كل فرع stage يقرر بنفسه سلوكه وقت السكوت

    if stage_type == "hook":
        if not session.get("intro_given"):
            session["intro_given"] = True
            return "INTRO_LESSON"
        return "GENERAL_COMMENT"   # لو لسه في hook وسبق قدّم، ميكررش نفس الانترو

    if stage_type == "game":
        return decide_game_action(stage["game_type"], stats, session)

    if stage_type == "teaching":
        if stats["questions"] > 0:
            return "ANSWER_QUESTION"
        if stats["answers"] >= 2:
            return "ASK_FOLLOWUP"
        return "GENERAL_COMMENT"   # ✅ ده اللي هيخلي الدرس يكمل طبيعي وقت السكوت

    if stage_type == "feedback":
        return "GIVE_CONFIDENCE_BOOST"

    if stage_type == "summary":
        if not session.get("outro_given"):
            session["outro_given"] = True
            return "OUTRO_LESSON"
        return "WAIT"

    return "GENERAL_COMMENT"
