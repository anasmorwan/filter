from groq import Groq
from prompts import TEACHER_SYSTEM_PROMPT, ACTION_PROMPTS, LECTURER_SYSTEM_PROMPT, JSON_SYSTEM_PROMPT
import os
from session import session, get_session_info, get_chat_history
import json
import re

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
            session["most_accurate_answers"] = [k.lower() for k in parsed_data.get("most_accurate_answers", [])]
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


"""
# النسخة الثانية
def generate_ai_response(action, messages):
    
    توليد الرد المناسب حسب action و context الرسائل
    

    context = list(messages)[-5:]
    prompt = build_prompt(action, context)

    raw_response = call_ai(prompt).strip()

    try:
        json_text = extract_json(raw_response)
        return json.loads(json_text)

    except json.JSONDecodeError:
        # محاولة إصلاح JSON
        try:
            fixed_json = heal_json(json_text)
            return json.loads(fixed_json)

        except Exception as e:
            print(f"❌ JSON Parsing Error: {e}\nRaw: {raw_response}")

            return {
                "response_text": "I had a bit of a glitch, let's continue our topic.",
                "expects_answer": False
            }


def generate_ai_response(action, messages):
    
    توليد الرد المناسب حسب action و context الرسائل

    context = list(messages)[-5:]  # آخر 5 رسائل فقط
    prompt = build_prompt(action, context)
    raw_response = call_ai(prompt).strip()
    
    # استخراج محتوى الـ JSON بدقة بين الأقواس
    try:
        start_idx = raw_response.find('{')
        end_idx = raw_response.rfind('}') + 1
        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON brackets found")
            
        json_content = raw_response[start_idx:end_idx]
        parsed_response = json.loads(json_content)
        return parsed_response
    except (json.JSONDecodeError, ValueError) as e:
        print(f"❌ JSON Parsing Error: {e}")
        return {
            "response_text": "I had a bit of a glitch, let's continue our topic.",
            "expects_answer": False
        }

"""




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
{JSON_SYSTEM_PROMPT}
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



"""
def extract_json(text):
    """
"""
    استخراج JSON من النص حتى لو احتوى على شرح أو markdown
    """
"""
    # إزالة markdown
    text = re.sub(r"```json|```", "", text)

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError("No JSON found")

    return match.group()

"""

def extract_json(text):
    """
    استخراج JSON من النص حتى لو كان داخله شرح أو markdown
    """

    # إزالة markdown
    text = re.sub(r"```json|```", "", text)

    # البحث عن أول JSON
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError("No JSON found")

    return match.group()

"""
def heal_json(text):
    """
"""
    إصلاح الأخطاء الشائعة في JSON القادم من الذكاء الاصطناعي
    """
"""
    # إزالة الفواصل الزائدة
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)

    # تحويل single quotes
    text = text.replace("'", '"')

    # إزالة newline داخل النص
    text = text.replace("\n", " ")

    return text

"""
def heal_json(text):
    """
    إصلاح الأخطاء الشائعة في JSON
    """

    # إزالة الفواصل الزائدة
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)

    # تحويل ' إلى "
    text = text.replace("'", '"')

    # إزالة newline داخل النصوص
    text = text.replace("\n", " ")

    return text
