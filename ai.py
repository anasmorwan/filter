from groq import Groq
from prompts import TEACHER_SYSTEM_PROMPT, ACTION_PROMPTS, LECTURER_SYSTEM_PROMPT, JSON_SYSTEM_PROMPT
import os
from session import get_session_info, get_chat_history
import json


# تهيئة العميل باستخدام مفتاح API الخاص بـ Groq
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def generate_ai_response(action, messages):
    """
    توليد الرد المناسب حسب action و context الرسائل
    """
    context = list(messages)[-5:]  # آخر 5 رسائل فقط
    prompt = build_prompt(action, context)
    raw_response = call_ai(prompt)
    
    # إزالة أي علامات Markdown قد يضيفها النموذج بالخطأ
    if raw_response.startswith("```json"):
        raw_response = raw_response[7:-3]
    elif raw_response.startswith("```"):
        raw_response = raw_response[3:-3]
        
    try:
        # تحويل النص إلى قاموس بايثون (Dictionary)
        parsed_response = json.loads(raw_response.strip())
        return parsed_response
    except json.JSONDecodeError as e:
        print(f"❌ JSON Parsing Error: {e}\nRaw Output: {raw_response}")
        # خطة طوارئ في حال فشل النموذج في إرجاع JSON صالح
        return {
            "response_text": "I lost my train of thought. Where were we?",
            "expects_answer": False
        }


def build_prompt(action, context_messages):
    session = get_session_info()
    mode = session.get("mode", "conversation")
    
    # --- جلب البيانات المشتركة ---
    full_conversation = get_chat_history()
    action_prompt = ACTION_PROMPTS.get(action, "")
    
    
    # --- الحالة الأولى: نمط المحاضرة (Lecture Mode) ---
    if mode == "lecture":
        chunks = session.get("lecture_chunks", [])
        idx = session.get("current_chunk_index", 0)
        current_material = chunks[idx] if idx < len(chunks) else "End of material."
        
        prompt = f"""
{JSON_SYSTEM_PROMPT}
{LECTURER_SYSTEM_PROMPT}

[LECTURE MATERIAL TO FOCUS ON NOW]:
{current_material}

[CONVERSATION CONTEXT]:
{full_conversation}

[YOUR SPECIFIC TASK]:
{action_prompt}

Instruction: Focus on the 'LECTURE MATERIAL'. If students ask unrelated questions, gently bring them back to the topic after answering briefly.
"""

    # --- الحالة الثانية: نمط المحادثة الحرة (القديم) ---
    else:
        topic = session.get("topic", "General English")
        level = session.get("difficulty", "Intermediate")
        prompt = f"""
{TEACHER_SYSTEM_PROMPT}
[SESSION CONTEXT]
- Topic: {topic} | Level: {level}

[HISTORY]
{full_conversation}

Teacher task: {action_prompt}
(Follow the context, don't invent names, be natural).
"""

    return prompt




'''
def build_prompt(action, context_messages):
    session = get_session_info()
    topic = session.get("topic", "General English")
    level = session.get("difficulty", "Intermediate")
    question = session.get("current_question", "None")
    
    # جلب المحادثة المتسلسلة (مدرس وطلاب)
    full_conversation = get_chat_history()

    action_prompt = ACTION_PROMPTS.get(action, "")

    prompt = f"""
{TEACHER_SYSTEM_PROMPT}

Current Active Question you asked (if any):
{question}
[CURRENT SESSION CONTEXT]
- Topic: {topic}
- Student Level: {level}

--- RECENT CONVERSATION HISTORY ---
{full_conversation}
-----------------------------------

Teacher task right now:
{action_prompt}
Important: Read the conversation history above. Your response MUST naturally follow the context of what was just said. Do not repeat your previous questions.
ONLY address users who have actually spoken in the [CONVERSATION HISTORY]. Do not invent names or talk to imaginary students.
    """
    return prompt

'''


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
    
