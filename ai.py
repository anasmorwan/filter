from groq import Groq
from prompts import TEACHER_SYSTEM_PROMPT, ACTION_PROMPTS, LECTURER_SYSTEM_PROMPT, JSON_SYSTEM_PROMPT, LEARNING_OBJECTIVES_PROMPT, capabilities
import os
from session import session, get_session_info, get_chat_history
import json
import re
from utils import heal_json, extract_json


# تهيئة العميل باستخدام مفتاح API الخاص بـ Groq
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

ALLOWED_UNDERSTANDING = {"good", "poor", "none"}


# النسخة الاخيرة    
def generate_ai_response(action, messages):

    prompt = build_prompt(action, messages)
    raw_response = call_ai(prompt).strip()

    try:

        json_text = extract_json(raw_response)

        try:
            parsed_data = json.loads(json_text)
            # --- إضافة طباعة التتبع (Debugging) ---
            print("\n" + "="*40)
            print("🔍 [AI JSON DEBUG]")
            print(f"🔹 Action: {action}")
            print(f"🔹 Response: {parsed_data.get('response_text', '')[:50]}...")
            print(f"🎯 Radar Keywords: {parsed_data.get('priority_keywords', [])}")
            print(f"✅ Bingo Keywords: {parsed_data.get('most_accurate_answers', [])}")
            print(f"📈 Understanding: {parsed_data.get('class_understanding', 'none')}")
            print("="*40 + "\n")
            # تحديث الجلسة بالكلمات المفتاحية الجديدة فور توليدها
            session["priority_keywords"] = [k.lower() for k in parsed_data.get("priority_keywords", [])]
            session["Bingo_Keywords"] = [k.lower() for k in parsed_data.get("most_accurate_answers", [])]
            # تفريغ حالة "الضربة الصائبة" السابقة
            session["bingo_answer_received"] = False 
    
    

        except json.JSONDecodeError:
            # محاولة إصلاح JSON
            fixed_json = heal_json(json_text)
            parsed_data = json.loads(fixed_json)
            # تحديث الجلسة بالكلمات المفتاحية الجديدة فور توليدها
            session["priority_keywords"] = [k.lower() for k in parsed_data.get("priority_keywords", [])]
            session["Bingo_Keywords"] = [k.lower() for k in parsed_data.get("most_accurate_answers", [])]
            # تفريغ حالة "الضربة الصائبة" السابقة
            session["bingo_answer_received"] = False 
    
    

        response_text = parsed_data.get("response_text", "")
        expects_answer = parsed_data.get("expects_answer", False)
        class_understanding = parsed_data.get("class_understanding", "none")
        most_accurate_answers = parsed_data.get("most_accurate_answers", "none")
        priority_keywords = parsed_data.get("priority_keywords", "none")

        
        # تصحيح نوع expects_answer
        if isinstance(expects_answer, str):
            expects_answer = expects_answer.lower() == "true"

        # التأكد من القيم المسموحة
        # if class_understanding not in ALLOWED_UNDERSTANDING:
            # class_understanding = "none"

        return {
            "response_text": response_text,
            "expects_answer": expects_answer,
            "class_understanding": class_understanding,
            "priority_keywords": priority_keywords,
            "most_accurate_answers": most_accurate_answers
        }

    except Exception as e:

        print(f"❌ AI JSON Error: {e}")
        print(f"Raw AI output: {raw_response}")

        return {
            "response_text": "I had a small glitch, let's continue.",
            "expects_answer": False,
            "class_understanding": "none",
            "most_accurate_answers": "none"
        }




def build_prompt(action, context_messages):
    session = get_session_info()
    mode = session.get("mode", "conversation")
    # نحصل على الأعداد من السيشن


    
    
    # --- جلب البيانات المشتركة ---
    full_conversation = get_chat_history()
    action_prompt = ACTION_PROMPTS.get(action, "")
    
    
    # --- الحالة الأولى: نمط المحاضرة (Lecture Mode) ---
    if mode == "lecture":
        chunks = session.get("lecture_chunks", [])
        idx = session.get("current_chunk_index", 0)
        current_material = chunks[idx] if idx < len(chunks) else "End of material."
        u_questions = session.get("urgent_questions", [])
        d_count = len(session.get("deferred_questions", []))
        # نرسل النصوص الكاملة للأسئلة العاجلة فقط
        urgent_text = "\n".join([m['text'] for m in u_questions])
        total_chunks = len(chunks)

        
        
        # 🎯 السحر هنا: حقن الأهداف فقط في بداية المحاضرة
        goals_context = ""
        if action == "INTRODUCE_LECTURE":
            goals = session.get("lecture_goals", "No goals defined.")
            goals_context = f"\n[GLOBAL LECTURE GOALS & OBJECTIVES]:\n{goals}\n"

        progress_context = ""
        if action != "INTRODUCE_LECTURE" and total_chunks > 0:
            # نحسب رقم الشريحة الحالية والقطع المتبقية
            current_slide_num = idx + 1
            remaining = total_chunks - current_slide_num
            progress_context = f"""
            [PROGRESS TRACKING]:
            - Current Slide: {current_slide_num} of {total_chunks}
            - Remaining Slides: {remaining}
            - Completion: {int((current_slide_num/total_chunks)*100)}%
            """
        questions_formatted = ""

        if action == "FINAL_Q_AND_A":
            deferred_qs = session.get("deferred_questions", [])
            questions_formatted = "\n".join(
                f"{i}. Student ({q['user']}): {q['text']}"
                for i, q in enumerate(deferred_qs, 1)
            )
        
        prompt = f"""
{JSON_SYSTEM_PROMPT}
{LECTURER_SYSTEM_PROMPT}

[SYSTEM CAPABILITIES - WHAT YOU CAN DO]:
{capabilities}


{goals_context}
{progress_context}

Urgent Questions to answer now: 
{urgent_text if u_questions else "None"}

{"STUDENT QUESTIONS:" if questions_formatted else ""}.


[LECTURE MATERIAL TO FOCUS ON NOW]:
{current_material}

[CONVERSATION CONTEXT]:
{full_conversation}

[YOUR SPECIFIC TASK]:
{action_prompt}

Instruction: Focus on the 'LECTURE MATERIAL'. If students ask unrelated questions, gently bring them back to the topic after answering briefly.

{"Remember to present the learning goals clearly to the students." if action == "INTRODUCE_LECTURE" else ""}
"""
    # --- الحالة الثانية: نمط المحادثة الحرة (القديم) ---
    else:
        topic = session.get("topic", "General English")
        level = session.get("difficulty", "Intermediate")
        prompt = f"""
{TEACHER_SYSTEM_PROMPT}
{JSON_SYSTEM_PROMPT}
[SESSION CONTEXT]
- Topic: {topic} | Level: {level}

[HISTORY]
{full_conversation}

Teacher task: {action_prompt}
(Follow the context, don't invent names, be natural).
"""

    return prompt


# دالة جديدة لتلخيص المستند بالكامل
def generate_global_summary(full_text):  
    prompt = LEARNING_OBJECTIVES_PROMPT.format(
    text=full_text[:4000]
    )
    # استدعاء الـ AI هنا لإنتاج الملخص
    summary_data = call_ai(prompt) 
    return summary_data


def call_ai(prompt):
    """
    تغيير طريقة الاتصال لتناسب Groq مع الحفاظ على اسم الدالة
    """
    response = client.chat.completions.create(
        # يمكنك أيضاً استخدام "mixtral-8x7b-32768" أو "llama3-8b-8192" للسرعة القصوى
        model="llama-3.3-70b-versatile", 
        messages=[
            {"role": "system", "content": "You are a helpful English teacher."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1024
    )
    return response.choices[0].message.content
