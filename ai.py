from groq import Groq
from prompts import TEACHER_SYSTEM_PROMPT, ACTION_PROMPTS
import os
from session import get_session_info, get_chat_history



# تهيئة العميل باستخدام مفتاح API الخاص بـ Groq
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def generate_ai_response(action, messages):
    """
    توليد الرد المناسب حسب action و context الرسائل
    """
    context = list(messages)[-5:]  # آخر 5 رسائل فقط
    prompt = build_prompt(action, context)
    response = call_ai(prompt)
    return response



def build_prompt(action, context_messages):
    session = get_session_info()
    question = session.get("current_question", "None")
    
    # جلب المحادثة المتسلسلة (مدرس وطلاب)
    full_conversation = get_chat_history()

    action_prompt = ACTION_PROMPTS.get(action, "")

    prompt = f"""
{TEACHER_SYSTEM_PROMPT}

Current Active Question you asked (if any):
{question}

--- RECENT CONVERSATION HISTORY ---
{full_conversation}
-----------------------------------

Teacher task right now:
{action_prompt}

Important: Read the conversation history above. Your response MUST naturally follow the context of what was just said. Do not repeat your previous questions.
    """
    return prompt

def build_prompt(action, context):
    """
    بناء prompt مع system + action prompt
    """
    session = get_session_info()
    question = session.get("current_question")
    # جلب المحادثة المتسلسلة (مدرس وطلاب)
    full_conversation = get_chat_history()

    
    # conversation = ""
    # for msg in context:
        # conversation += f"{msg['user']}: {msg['text']}\n"

    action_prompt = ACTION_PROMPTS.get(action, "")

    prompt = f"""
{TEACHER_SYSTEM_PROMPT}

Current Active Question you asked (if any):
{question}

--- RECENT CONVERSATION HISTORY ---
{full_conversation}
-----------------------------------

Teacher task right now:
{action_prompt}

Important: Read the conversation history above. Your response MUST naturally follow the context of what was just said. Do not repeat your previous questions.
    """
    return prompt

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
