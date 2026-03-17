from groq import Groq
from prompts import build_prompt
import os
from session import session, get_session_info, get_chat_history
import json
import re
from utils import heal_json, extract_json
from openai import OpenAI
from google import genai
import requests
import cohere
import traceback
import logging
import asyncio


# تهيئة العميل باستخدام مفتاح API الخاص بـ Groq
# client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")



from google import genai
from groq import Groq
import logging

# 1️⃣ Gemini
gemini_model = None
if GEMINI_API_KEY:
    try:
        gemini_model = genai.Client(api_key=GEMINI_API_KEY)
        logging.info("✅ 1. Gemini configured successfully")
    except Exception as e:
        logging.warning(f"❌ Gemini failed: {e}")

# 2️⃣ Groq
groq_client = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        logging.info("✅ 2. Groq configured successfully")
    except Exception as e:
        logging.warning(f"❌ Groq failed: {e}")

# 3️⃣ OpenRouter
if OPENROUTER_API_KEY:
    logging.info("✅ 3. OpenRouter configured successfully")
    
# 4. إعداد Cohere
cohere_client = None
if COHERE_API_KEY:
    try:
        cohere_client = cohere.Client(COHERE_API_KEY)
        logging.info("✅ 4. Cohere configured successfully")
    except Exception as e:
        logging.warning(f"⚠️ Could not configure Cohere: {e}")




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

# --- الدالة الموحدة لتوليد الردود ---

def generate_smart_response(prompt: str) -> str:
    """
    Tries to generate a response by attempting a chain of services silently.
    It logs errors for the developer but does not send progress messages to the user.
    """
    timeout_seconds = 45


    #  1️⃣ Cohere
    if cohere_client:
        try:
            logging.info("Attempting request with: 5. Cohere...")
            response = cohere_client.chat(model='command-r', message=prompt, temperature=0.8)
            logging.info("✅ Success with Cohere.")
            return response.text
        except Exception as e:
            logging.warning(f"❌ Cohere failed: {e}")



    # 2️⃣ Google Gemini
    if gemini_model:
        try:
            logging.info("Attempting request with: 1. Google Gemini...")

            response = gemini_model.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

            if response and response.text:
                logging.info("✅ Success with Gemini.")
                return response.text.strip()

            logging.warning("❌ Gemini returned empty response. Trying fallback...")

        except Exception as e:
            logging.warning(f"❌ Gemini failed: {e}")


    # 3️⃣ Groq (LLaMA 3.3)
    if groq_client:
        try:
            logging.info("Attempting request with: 2. Groq (LLaMA 3.3)...")

            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
            )

            result = chat_completion.choices[0].message.content

            if result:
                logging.info("✅ Success with Groq.")
                return result.strip()

            logging.warning("❌ Groq returned empty response. Trying fallback...")

        except Exception as e:
            logging.warning(f"❌ Groq failed: {e}")


    # 4️⃣ OpenRouter
    if OPENROUTER_API_KEY:
        try:
            logging.info("Attempting request with: 3. OpenRouter...")
    
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://t.me/Oiuhelper_bot",
                "X-Title": "AI Quiz Bot"
            }

            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={
                    "model": "google/gemma-2-9b-it",
                    "messages": [
                    {"role": "user", "content": prompt}
                    ]
                },
                timeout=timeout_seconds
            )

            response.raise_for_status()

            data = response.json()

            result_text = data["choices"][0]["message"]["content"]

            if result_text:
                logging.info("✅ Success with OpenRouter.")
                return result_text.strip()

            logging.warning("❌ OpenRouter returned empty response.")

        except Exception as e:
            logging.warning(f"❌ OpenRouter failed: {e}")


    # 🚫 All models failed
    logging.error("❌ All API providers failed. Returning empty string.")
    return ""


# دالة جديدة لتلخيص المستند بالكامل
async def generate_global_summary(full_text):  
    prompt = LEARNING_OBJECTIVES_PROMPT.format(
    text=full_text[:4000]
    )
    # استدعاء الـ AI هنا لإنتاج الملخص
    try:
        summary_data = await asyncio.to_thread(call_ai, prompt) 
        return summary_data
    except Exception as e:
        print(f"Error in global summary: {e}")
        return "Lecture objectives: Understanding the core concepts of this material."





def call_ai(prompt):
    """
    تغيير طريقة الاتصال لتناسب Groq مع الحفاظ على اسم الدالة
    """
    response = generate_smart_response(prompt)
        
    return response





"""

def call_ai(prompt):
    """
"""
    تغيير طريقة الاتصال لتناسب Groq مع الحفاظ على اسم الدالة
    """
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
